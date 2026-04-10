package com.google.mediapipe.examples.llminference

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.autolife.shared.platform.WifiNetworkProvider

class WifiScanner(private val context: Context) : WifiNetworkProvider {
    companion object {
        private const val TAG = "WifiScanner"
    }

    override fun getVisibleNetworks(): List<String> = getWifiNetworks()

    fun getWifiNetworks(): List<String> {
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

            filteredNetworks
        } catch (e: SecurityException) {
            Log.e(TAG, "Security exception while scanning WiFi", e)
            listOf("Security Error: ${e.message}")
        } catch (e: Exception) {
            Log.e(TAG, "Unexpected error in WifiScanner", e)
            listOf("Error: ${e.message}")
        }
    }
}