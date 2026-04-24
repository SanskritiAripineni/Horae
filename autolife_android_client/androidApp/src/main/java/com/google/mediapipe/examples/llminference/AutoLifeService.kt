package com.google.mediapipe.examples.llminference

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
class AutoLifeService : Service() {

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var analyzer: SequentialMotionLocationAnalyzer? = null
    @Volatile private var isRunning = false
    private var permanentMotionDetector: MotionDetector? = null
    private var lightMonitor: LightSensorMonitor? = null
    private var sleepStateReceiver: SleepStateReceiver? = null
    private val analysisScheduler = AdaptiveAnalysisScheduler(
        baseIntervalMs = LOG_INTERVAL,
        demoIntervalMs = DEMO_LOG_INTERVAL
    )
    private val journalAttemptThrottle = JournalAttemptThrottle(
        baseRetryMs = JOURNAL_RETRY_BACKOFF,
        demoRetryMs = DEMO_JOURNAL_RETRY_BACKOFF
    )

    companion object {
        private const val CHANNEL_ID = "AutoLifeChannel"
        private const val NOTIFICATION_ID = 1
        private const val LOG_INTERVAL = 60_000L // 1 minute
        private const val DEMO_LOG_INTERVAL = 30_000L // 30 seconds
        private const val JOURNAL_INTERVAL = 30 * 60_000L // 30 minutes
        private const val DEMO_JOURNAL_INTERVAL = 2 * 60_000L // 2 minutes
        private const val JOURNAL_RETRY_BACKOFF = 5 * 60_000L // 5 minutes
        private const val DEMO_JOURNAL_RETRY_BACKOFF = 60_000L // 1 minute
    }

    private var lastAnalysisSignature: String? = null

    override fun onCreate() {
        super.onCreate()
        analyzer = SequentialMotionLocationAnalyzer(this)
        createNotificationChannel()
        lightMonitor = LightSensorMonitor(this).also { it.start() }
        sleepStateReceiver = SleepStateReceiver(lightMonitor!!).also { receiver ->
            val filter = IntentFilter().apply {
                addAction(Intent.ACTION_SCREEN_OFF)
                addAction(Intent.ACTION_SCREEN_ON)
            }
            registerReceiver(receiver, filter)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!hasLocationPermission()) {
            Log.w("AutoLifeService", "Cannot start AutoLife service without location permission")
            isRunning = false
            com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
            stopSelf(startId)
            return START_NOT_STICKY
        }

        if (!isRunning) {
            isRunning = true
            if (!startForegroundService()) {
                isRunning = false
                com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
                stopSelf(startId)
                return START_NOT_STICKY
            }
            startLoop()
            startPermanentMotionObserver()
        }
        com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(true)
        return START_STICKY
    }

    private fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun startForegroundService(): Boolean {
        val pendingIntent: PendingIntent = Intent(this, MainActivity::class.java).let { notificationIntent ->
            PendingIntent.getActivity(this, 0, notificationIntent, PendingIntent.FLAG_IMMUTABLE)
        }

        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("AutoLife Recording")
            .setContentText("Logging your life context in the background...")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                startForeground(
                    NOTIFICATION_ID, notification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION or
                        android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                )
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
            return true
        } catch (e: SecurityException) {
            Log.w("AutoLifeService", "Cannot promote AutoLife service to a location foreground service", e)
            return false
        }
    }

    private fun startLoop() {
        serviceScope.launch {
            while (isActive && isRunning) {
                val cycleStartedAt = System.currentTimeMillis()
                val analysisResult = startAnalysisCycle()
                lastAnalysisSignature = analysisResult.materialContextSignature()
                val isDemo = com.google.mediapipe.examples.llminference.data.DebugRepository.isDemoMode.value
                val currentInterval = if (isDemo) DEMO_JOURNAL_INTERVAL else JOURNAL_INTERVAL
                val now = System.currentTimeMillis()

                if (journalAttemptThrottle.shouldAttempt(
                        nowMs = now,
                        journalIntervalMs = currentInterval,
                        contextSignature = lastAnalysisSignature,
                        isDemoMode = isDemo
                    )
                ) {
                    val journalGenerator = JournalGenerator(this@AutoLifeService)
                    val generated = journalGenerator.tryGenerateJournal(now, currentInterval)
                    journalAttemptThrottle.onAttemptFinished(
                        nowMs = now,
                        success = generated,
                        contextSignature = lastAnalysisSignature,
                        journalIntervalMs = currentInterval,
                        isDemoMode = isDemo
                    )
                }

                val cycleDuration = System.currentTimeMillis() - cycleStartedAt
                val delayMs = analysisScheduler.nextDelayMs(
                    result = analysisResult,
                    cycleDurationMs = cycleDuration,
                    isDemoMode = isDemo
                )
                delay(delayMs)
            }
        }
    }

    private suspend fun startAnalysisCycle() = try {
        analyzer?.analyzeOnce(sharedMotionDetector = permanentMotionDetector) { result, phase ->
            Log.d("AutoLifeService", "Analysis phase=$phase result=$result")
        }
    } catch (e: Exception) {
        Log.w("AutoLifeService", "Analysis cycle timed out or failed", e)
        null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "AutoLife Background Service",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
        sleepStateReceiver?.let { unregisterReceiver(it) }
        sleepStateReceiver = null
        lightMonitor?.stop()
        lightMonitor = null
        analyzer?.close()
        permanentMotionDetector?.stopDetection()
        serviceScope.cancel()
    }

    private fun startPermanentMotionObserver() {
        if (!BuildConfig.DEBUG) {
            com.google.mediapipe.examples.llminference.data.DebugRepository.setPermanentMotionEnabled(false)
            return
        }
        serviceScope.launch {
            com.google.mediapipe.examples.llminference.data.DebugRepository.isPermanentMotionEnabled.collectLatest { enabled ->
                if (enabled) {
                    if (permanentMotionDetector == null) {
                        permanentMotionDetector = MotionDetector(this@AutoLifeService)
                        permanentMotionDetector?.startDetection { /* debug UI updates handled internally */ }
                    }
                } else {
                    permanentMotionDetector?.stopDetection()
                    permanentMotionDetector = null
                }
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}
