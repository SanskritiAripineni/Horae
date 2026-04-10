package com.google.mediapipe.examples.llminference

import android.app.Application
import com.autolife.composeapp.platform.PlatformStateProvider
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
        PlatformStateProvider.onDemoModeChanged = { DebugRepository.setDemoMode(it) }
        PlatformStateProvider.onPermanentMotionChanged = { DebugRepository.setPermanentMotionEnabled(it) }
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
    }
}
