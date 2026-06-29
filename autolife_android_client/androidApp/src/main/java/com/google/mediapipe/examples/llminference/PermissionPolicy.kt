package com.google.mediapipe.examples.llminference

import android.Manifest
import android.os.Build

object PermissionPolicy {
    fun requiredRuntimePermissions(sdkInt: Int = Build.VERSION.SDK_INT): Array<String> {
        val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (sdkInt >= Build.VERSION_CODES.Q) {
            permissions += Manifest.permission.ACTIVITY_RECOGNITION
        }
        return permissions.toTypedArray()
    }

    fun optionalRuntimePermissions(sdkInt: Int = Build.VERSION.SDK_INT): Array<String> {
        val permissions = mutableListOf<String>()
        if (sdkInt >= Build.VERSION_CODES.TIRAMISU) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
            permissions += Manifest.permission.NEARBY_WIFI_DEVICES
        }
        return permissions.toTypedArray()
    }

    fun coverageLabel(permission: String): String = when (permission) {
        Manifest.permission.POST_NOTIFICATIONS -> "notifications"
        Manifest.permission.NEARBY_WIFI_DEVICES -> "Wi-Fi context"
        Manifest.permission.ACTIVITY_RECOGNITION -> "motion"
        Manifest.permission.ACCESS_FINE_LOCATION -> "location"
        Manifest.permission.ACCESS_COARSE_LOCATION -> "approximate location"
        else -> permission.substringAfterLast('.').lowercase().replace('_', ' ')
    }
}
