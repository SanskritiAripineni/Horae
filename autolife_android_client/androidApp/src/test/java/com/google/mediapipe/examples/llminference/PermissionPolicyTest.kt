package com.google.mediapipe.examples.llminference

import android.Manifest
import android.os.Build
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class PermissionPolicyTest {
    @Test
    fun requiredPermissionsIncludeLocationAndModernMotion() {
        assertArrayEquals(
            arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACTIVITY_RECOGNITION,
            ),
            PermissionPolicy.requiredRuntimePermissions(Build.VERSION_CODES.Q),
        )
    }

    @Test
    fun requiredPermissionsBeforeActivityRecognitionOnlyNeedLocation() {
        assertArrayEquals(
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
            PermissionPolicy.requiredRuntimePermissions(Build.VERSION_CODES.P),
        )
    }

    @Test
    fun optionalPermissionsAreSeparatedFromCoreCollection() {
        assertArrayEquals(
            arrayOf(
                Manifest.permission.POST_NOTIFICATIONS,
                Manifest.permission.NEARBY_WIFI_DEVICES,
            ),
            PermissionPolicy.optionalRuntimePermissions(Build.VERSION_CODES.TIRAMISU),
        )
    }

    @Test
    fun optionalPermissionLabelsAreReviewerReadable() {
        assertEquals("Wi-Fi context", PermissionPolicy.coverageLabel(Manifest.permission.NEARBY_WIFI_DEVICES))
    }
}
