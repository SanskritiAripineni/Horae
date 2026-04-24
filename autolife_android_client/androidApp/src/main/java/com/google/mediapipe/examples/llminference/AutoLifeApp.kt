package com.google.mediapipe.examples.llminference

import android.Manifest
import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import androidx.core.content.ContextCompat
import com.autolife.composeapp.platform.AppContextHolder
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.platform.BatteryDeviceInfo
import com.autolife.composeapp.platform.BatteryRunEnvironment
import com.autolife.shared.ai.AiClientProvider
import com.autolife.shared.ai.GeminiAiClient
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.db.createAndroidDriver
import com.autolife.shared.network.AutoLifeApi
import android.widget.Toast
import com.google.mediapipe.examples.llminference.data.DataExporter
import com.google.mediapipe.examples.llminference.data.DebugRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class AutoLifeApp : Application() {

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate() {
        super.onCreate()
        AppContextHolder.context = applicationContext
        AutoLifeApi.init(BuildConfig.BACKEND_URL)
        DatabaseRepository.init(createAndroidDriver(this))
        AiClientProvider.init(GeminiAiClient(BuildConfig.GEMINI_API_KEY))
        bridgeDebugToPlatformState()
    }

    /** Forward DebugRepository updates into PlatformStateProvider for the CMP UI. */
    private fun bridgeDebugToPlatformState() {
        appScope.launch {
            DebugRepository.motionStats.collect { m ->
                PlatformStateProvider.updateMotion(
                    acceleration = m.acceleration,
                    stepCount = m.stepCount,
                    speed = m.speed,
                    altitude = m.altitude,
                    detectedClass = m.detectedClass,
                )
            }
        }
        appScope.launch {
            DebugRepository.isServiceRunning.collect { running ->
                PlatformStateProvider.updateServiceState(
                    isRunning = running,
                    isDemoMode = DebugRepository.isDemoMode.value,
                )
            }
        }
        appScope.launch {
            DebugRepository.isDemoMode.collect { demo ->
                PlatformStateProvider.updateServiceState(
                    isRunning = DebugRepository.isServiceRunning.value,
                    isDemoMode = demo,
                )
            }
        }
        appScope.launch {
            DebugRepository.locationInfo.collect { loc ->
                PlatformStateProvider.updateLocation(
                    latitude = loc.latitude,
                    longitude = loc.longitude,
                    ssids = loc.ssids,
                    inference = loc.lastInference,
                    mapPreviewBytes = loc.mapImageBytes,
                    geocoderContext = loc.geocoderContext,
                    osmContext = loc.osmContext,
                    wifiContext = loc.wifiContext,
                    inferenceSource = loc.inferenceSource,
                )
            }
        }
        appScope.launch {
            DebugRepository.lastJournal.collect { journal ->
                PlatformStateProvider.updateLastJournal(journal)
            }
        }
        appScope.launch {
            DebugRepository.isPermanentMotionEnabled.collect { enabled ->
                PlatformStateProvider.updatePermanentMotion(enabled)
            }
        }

        // Register action callbacks so the cross-platform DevDashboardScreen
        // can trigger Android-specific operations.
        val appContext = this
        PlatformStateProvider.isDebugBuild = BuildConfig.DEBUG
        PlatformStateProvider.onDemoModeChanged = { DebugRepository.setDemoMode(it) }
        PlatformStateProvider.onPermanentMotionChanged = {
            DebugRepository.setPermanentMotionEnabled(it && BuildConfig.DEBUG)
        }
        PlatformStateProvider.onExportRequested = {
            appScope.launch {
                val ok = DataExporter.exportJournals(appContext)
                Toast.makeText(
                    appContext,
                    if (ok) "Exported to Downloads/AutoLife" else "Export failed",
                    Toast.LENGTH_LONG,
                ).show()
            }
        }
        PlatformStateProvider.onGenerateJournalRequested = {
            appScope.launch {
                val ok = JournalGenerator(appContext).tryGenerateJournal(
                    endTime = System.currentTimeMillis(),
                    periodDurationMs = 2 * 60_000L,
                )
                withContext(Dispatchers.Main) {
                    Toast.makeText(
                        appContext,
                        if (ok) "Journal generated" else "No logs in last 2 min — start service first",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }
        }
        PlatformStateProvider.onServiceToggleRequested = { shouldStart ->
            val intent = Intent(appContext, AutoLifeService::class.java)
            if (shouldStart) {
                if (!hasLocationPermission()) {
                    Toast.makeText(
                        appContext,
                        "Location permission is required before AutoLife can record in the background.",
                        Toast.LENGTH_LONG,
                    ).show()
                    appScope.launch {
                        kotlinx.coroutines.delay(100)
                        PlatformStateProvider.updateServiceState(false)
                    }
                } else if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    appContext.startForegroundService(intent)
                } else {
                    appContext.startService(intent)
                }
            } else {
                appContext.stopService(intent)
            }
        }
        PlatformStateProvider.setPlatformName("Android")
        PlatformStateProvider.onBatteryLevelRequested = {
            currentBatteryPercent()
        }
        PlatformStateProvider.onBatteryDeviceInfoRequested = {
            BatteryDeviceInfo(
                platform = "Android",
                deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}",
                osVersion = "Android ${Build.VERSION.RELEASE}",
                appVersion = currentAppVersion(),
            )
        }
        PlatformStateProvider.onBatteryEnvironmentRequested = {
            BatteryRunEnvironment(
                networkSummary = currentNetworkSummary(),
                lowPowerModeEnabled = isLowPowerModeEnabled(),
            )
        }
        PlatformStateProvider.onBatteryAssessmentExportRequested = { report ->
            appScope.launch {
                val ok = DataExporter.exportBatteryReport(appContext, report)
                withContext(Dispatchers.Main) {
                    Toast.makeText(
                        appContext,
                        if (ok) "Battery report exported" else "Battery report export failed",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }
        }
        PlatformStateProvider.onBatteryAssessmentCompleted = { record ->
            appScope.launch {
                withContext(Dispatchers.Main) {
                    Toast.makeText(
                        appContext,
                        "Battery run saved: ${record.batteryDropPercent}% drop in ${record.durationMinutes.toInt()} min",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }
        }
        PlatformStateProvider.loadBatteryAssessments()
        PlatformStateProvider.refreshBatteryLevel()
    }

    private fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun currentBatteryPercent(): Int? {
        val batteryIntent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return null
        val level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        if (level < 0 || scale <= 0) return null
        return ((level * 100f) / scale).toInt()
    }

    private fun currentAppVersion(): String {
        val pkg = packageManager.getPackageInfo(packageName, 0)
        val versionName = pkg.versionName ?: "unknown"
        val versionCode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            pkg.longVersionCode.toString()
        } else {
            @Suppress("DEPRECATION")
            pkg.versionCode.toString()
        }
        return "$versionName ($versionCode)"
    }

    private fun isLowPowerModeEnabled(): Boolean {
        val powerManager = getSystemService(Context.POWER_SERVICE) as? PowerManager
        return powerManager?.isPowerSaveMode ?: false
    }

    private fun currentNetworkSummary(): String {
        val connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return "Network unavailable"
        val capabilities = connectivityManager.getNetworkCapabilities(connectivityManager.activeNetwork)
            ?: return "No active network"
        val transport = when {
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "Cellular"
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
            else -> "Other"
        }
        val internet = if (capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
            "internet"
        } else {
            "limited"
        }
        return "$transport, $internet"
    }
}
