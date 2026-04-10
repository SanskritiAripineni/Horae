package com.autolife.shared.platform

/**
 * Cross-platform platform service interfaces.
 * Android: implemented by existing classes with native sensor/location APIs.
 * iOS: will be implemented with CoreLocation, CoreMotion, MapKit, etc.
 */

data class LocationData(
    val latitude: Double,
    val longitude: Double,
    val speed: Double = 0.0,
    val altitude: Double = 0.0
)

/** Provides the device's current GPS location. */
interface LocationProvider {
    suspend fun getCurrentLocation(): LocationData?
}

/** Scans for visible Wi-Fi network SSIDs. */
interface WifiNetworkProvider {
    fun getVisibleNetworks(): List<String>
}

/** Fetches a static map image as raw bytes for a given coordinate. */
interface MapImageFetcher {
    suspend fun fetchMapImage(latitude: Double, longitude: Double): ByteArray?
}

/**
 * Provides hardware motion sensor data (accelerometer, step counter, barometer, GPS speed).
 * The implementation runs the shared [com.autolife.shared.analyzer.MotionClassifier] internally
 * and reports classified motion types via the callback.
 */
interface MotionSensorProvider {
    fun startDetection(callback: (List<String>) -> Unit)
    fun stopDetection()
    fun getMotionHistory(): String?
    fun clearMotionHistory(): Boolean
}
