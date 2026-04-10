package com.autolife.composeapp.platform

import androidx.compose.runtime.Composable

/** Platform-specific service toggle (Android: starts/stops foreground service, iOS: stub). */
@Composable
expect fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit)

/** Platform-specific dev dashboard route. Android shows full debug screen, iOS shows placeholder. */
@Composable
expect fun DevDashboardRoute(onBackClick: () -> Unit)

/** Returns today's date as "yyyy-MM-dd". Platform-specific because KMP has no common wall-clock API. */
expect fun currentDateKey(): String
