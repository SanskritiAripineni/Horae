package com.autolife.composeapp.platform

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.ImageBitmap
import com.autolife.shared.model.RawDayMarkers

/** Platform-specific service toggle (Android: starts/stops foreground service, iOS: stub). */
@Composable
expect fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit)

/** Platform-specific dev dashboard route. Android shows full debug screen, iOS shows placeholder. */
@Composable
expect fun DevDashboardRoute(onBackClick: () -> Unit)

/** Returns today's date as "yyyy-MM-dd". Platform-specific because KMP has no common wall-clock API. */
expect fun currentDateKey(): String

/** Decodes the map preview bytes captured for the current location, if supported on the platform. */
@Composable
expect fun rememberLocationPreviewImage(imageBytes: ByteArray?): ImageBitmap?

/**
 * Aggregates StudentLife-style behavioral marker dicts for the last [nDays] days from
 * local sensor data. Android: derives mobility_entropy, location_revisit_ratio, and
 * social_rhythm_metric from ContextLog records. iOS: returns empty list (stub).
 */
expect suspend fun getBehavioralMarkers(nDays: Int): List<RawDayMarkers>

/** Opens the user's default system calendar app. Android: Calendar intent. iOS: calshow:// */
expect fun openNativeCalendar()
