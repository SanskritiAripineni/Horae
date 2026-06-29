package com.google.mediapipe.examples.llminference

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.SensorLog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Records screen-off/on transitions for sleep detection.
 *
 * Each event is written to SQLDelight as type="SLEEP_STATE" with JSON:
 *   {"event":"screen_off","ts":1714234567890,"lux":3.2}
 *
 * The lux field (from LightSensorMonitor) distinguishes dark-room sleep
 * from idle phone-locked events — low lux (<20) strongly corroborates sleep.
 * Must be registered programmatically (ACTION_SCREEN_OFF/ON cannot be declared in manifest).
 */
class SleepStateReceiver(
    private val lightMonitor: LightSensorMonitor,
) : BroadcastReceiver() {
    private val ioScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onReceive(context: Context, intent: Intent) {
        val event = when (intent.action) {
            Intent.ACTION_SCREEN_OFF -> "screen_off"
            Intent.ACTION_SCREEN_ON -> "screen_on"
            else -> return
        }
        val nowMs = System.currentTimeMillis()
        val lux = lightMonitor.lastLux
        val content = if (lux != null)
            """{"event":"$event","ts":$nowMs,"lux":$lux}"""
        else
            """{"event":"$event","ts":$nowMs}"""

        val pendingResult = goAsync()
        ioScope.launch {
            try {
                DatabaseRepository.insertLog(
                    SensorLog(timestamp = nowMs, type = "SLEEP_STATE", content = content)
                )
            } catch (e: Exception) {
                Log.w("SleepStateReceiver", "Failed to log $event", e)
            } finally {
                pendingResult.finish()
            }
        }
    }
}
