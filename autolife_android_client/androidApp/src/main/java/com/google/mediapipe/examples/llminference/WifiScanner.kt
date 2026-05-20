package com.google.mediapipe.examples.llminference

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.autolife.shared.platform.WifiNetworkProvider
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class WifiScanner(private val context: Context) : WifiNetworkProvider {
    companion object {
        private const val TAG = "WifiScanner"
        private const val FORCE_SCAN_TIMEOUT_MS = 2_000L
        private data class CachedWifiSnapshot(
            val ssids: List<String>,
            val capturedAtMs: Long
        )

        @Volatile
        private var cachedSnapshot: CachedWifiSnapshot? = null

        fun createFingerprint(ssids: List<String>): String =
            ssids.map { it.trim() }
                .filter { it.isNotEmpty() }
                .distinct()
                .sorted()
                .joinToString("|")
                .hashCode()
                .toString()
    }

    override fun getVisibleNetworks(): List<String> = getWifiNetworks()

    fun getWifiNetworks(
        maxAgeMs: Long = 0L,
        forceRefresh: Boolean = false
    ): List<String> {
        val now = System.currentTimeMillis()
        cachedSnapshot
            ?.takeIf { !forceRefresh && maxAgeMs > 0L && now - it.capturedAtMs <= maxAgeMs }
            ?.let { cached ->
                Log.d(TAG, "Reusing cached WiFi scan with ${cached.ssids.size} SSIDs")
                return cached.ssids
            }

        val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as WifiManager

        if (!wifiManager.isWifiEnabled) {
            Log.w(TAG, "WiFi is disabled")
            return listOf("WiFi is disabled")
        }

        // Check for location permission
        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "Location permission not granted - mandatory for WiFi scanning result access")
            return listOf("Permission Denied: ACCESS_FINE_LOCATION")
        }

        return try {
            if (forceRefresh) {
                awaitFreshScan(wifiManager)
            }
            val results = wifiManager.scanResults

            if (results == null) {
                Log.w(TAG, "scanResults returned null")
                return listOf("Scan results null")
            }

            Log.d(TAG, "Found ${results.size} raw scan results")
            
            val filteredNetworks = results
                .mapNotNull { result ->
                    result.SSID.takeIf { it.isNotEmpty() }
                }
                .distinct()

            Log.d(TAG, "Filtered to ${filteredNetworks.size} unique SSIDs")
            
            if (filteredNetworks.isEmpty()) {
                Log.w(TAG, "No SSIDs found in scan results. Is Location service (GPS) enabled?")
                return listOf("No visible Wi-Fi SSIDs")
            }

            cachedSnapshot = CachedWifiSnapshot(
                ssids = filteredNetworks,
                capturedAtMs = now
            )
            filteredNetworks
        } catch (e: SecurityException) {
            Log.e(TAG, "Security exception while scanning WiFi", e)
            listOf("Security Error: ${e.message}")
        } catch (e: Exception) {
            Log.e(TAG, "Unexpected error in WifiScanner", e)
            listOf("Error: ${e.message}")
        }
    }

    private fun awaitFreshScan(wifiManager: WifiManager) {
        val latch = CountDownLatch(1)
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action == WifiManager.SCAN_RESULTS_AVAILABLE_ACTION) {
                    latch.countDown()
                }
            }
        }

        val registered = runCatching {
            ContextCompat.registerReceiver(
                context,
                receiver,
                IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION),
                ContextCompat.RECEIVER_NOT_EXPORTED,
            )
        }.isSuccess

        try {
            @Suppress("DEPRECATION")
            val started = wifiManager.startScan()
            if (!started) {
                Log.w(TAG, "Fresh WiFi scan request was throttled or rejected; using latest available results")
                return
            }
            latch.await(FORCE_SCAN_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        } catch (e: SecurityException) {
            Log.w(TAG, "Fresh WiFi scan request missing permission; using latest available results", e)
        } catch (e: InterruptedException) {
            Thread.currentThread().interrupt()
        } finally {
            if (registered) {
                runCatching { context.unregisterReceiver(receiver) }
            }
        }
    }
}
