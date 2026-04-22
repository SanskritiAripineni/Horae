package com.autolife.composeapp.platform

import android.content.Context

/**
 * Holds a reference to the application Context for use by androidMain-only
 * platform code that runs outside composables (e.g. BehavioralMarkerAggregator).
 * Set once in AutoLifeApp.onCreate() before any analysis runs.
 */
object AppContextHolder {
    @Volatile var context: Context? = null
}
