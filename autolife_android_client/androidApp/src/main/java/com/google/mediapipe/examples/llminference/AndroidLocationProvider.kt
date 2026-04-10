package com.google.mediapipe.examples.llminference

import android.content.Context
import com.autolife.shared.platform.LocationData
import com.autolife.shared.platform.LocationProvider

class AndroidLocationProvider(private val context: Context) : LocationProvider {

    override suspend fun getCurrentLocation(): LocationData? {
        val location = getBestLocation(context) ?: return null
        return LocationData(
            latitude = location.latitude,
            longitude = location.longitude,
            speed = location.speed.toDouble(),
            altitude = location.altitude
        )
    }
}
