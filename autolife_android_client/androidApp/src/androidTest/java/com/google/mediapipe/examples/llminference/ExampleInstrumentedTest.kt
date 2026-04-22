package com.google.mediapipe.examples.llminference

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test, which will execute on an Android device.
 *
 * See [testing documentation](http://d.android.com/tools/testing).
 */
@RunWith(AndroidJUnit4::class)
class ExampleInstrumentedTest {
    @Test
    fun useAppContext() {
        // Context of the app under test.
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals("com.google.mediapipe.examples.llminference", appContext.packageName)
    }

    @Test
    fun reverseGeocodeLocation_returnsAddressSummary() = runBlocking {
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext

        val summary = reverseGeocodeLocation(
            context = appContext,
            latitude = 37.4219999,
            longitude = -122.0840575
        )

        assertFalse("Expected geocoder summary for known coordinates", summary.isNullOrBlank())
    }
}
