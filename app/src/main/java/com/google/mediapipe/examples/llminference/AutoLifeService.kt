package com.google.mediapipe.examples.llminference

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.google.mediapipe.examples.llminference.data.LogDao
import com.google.mediapipe.examples.llminference.data.SensorLog
import kotlinx.coroutines.*

class AutoLifeService : Service() {

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var analyzer: SequentialMotionLocationAnalyzer? = null
    private var isRunning = false
    private lateinit var logDao: LogDao

    companion object {
        private const val CHANNEL_ID = "AutoLifeChannel"
        private const val NOTIFICATION_ID = 1
        private const val LOG_INTERVAL = 60_000L // 1 minute
    }

    override fun onCreate() {
        super.onCreate()
        logDao = (application as AutoLifeApp).database.logDao()
        analyzer = SequentialMotionLocationAnalyzer(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!isRunning) {
            isRunning = true
            startForegroundService()
            startLoop()
        }
        return START_STICKY
    }

    private fun startForegroundService() {
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

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {     
             startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun startLoop() {
        serviceScope.launch {
            while (isActive && isRunning) {
                // Trigger analysis
                val timestamp = System.currentTimeMillis()
                // logDao.insertLog(SensorLog(timestamp = timestamp, type = "SYSTEM", content = "Starting periodic analysis"))
                
                startAnalysisCycle()

                delay(LOG_INTERVAL)
            }
        }
    }

    private suspend fun startAnalysisCycle() {
        val deferred = CompletableDeferred<Unit>()
        
        // We need to run this on Main thread because MotionDetector internal logic might expect it (though we fixed it ideally to be thread safe, standard sensor listeners are main thread)
        withContext(Dispatchers.Main) {
            analyzer?.startAnalysis { result, phase ->
               // We can log intermediate phases if we want, or just wait for complete
               if (phase == SequentialMotionLocationAnalyzer.AnalysisPhase.COMPLETE) {
                   deferred.complete(Unit)
               }
            }
        }
        
        // Wait for it to finish or timeout to prevent hanging
        try {
            withTimeout(30_000L) { // 30 seconds max for analysis
                deferred.await()
            }
        } catch (e: Exception) {
            // log error
        }
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
        analyzer?.close()
        serviceScope.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }
}
