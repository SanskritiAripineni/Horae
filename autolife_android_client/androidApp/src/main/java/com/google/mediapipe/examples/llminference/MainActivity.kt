package com.google.mediapipe.examples.llminference

import android.os.Build
import android.Manifest
import android.content.ComponentCallbacks2
import android.os.Bundle
import android.os.StrictMode
import android.util.Log
import android.view.Choreographer
import androidx.activity.ComponentActivity
import android.content.Intent
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import com.autolife.composeapp.AutoLifeApp
import com.autolife.shared.repository.AnalysisRepository

class MainActivity : ComponentActivity() {

    private var frameCallback: Choreographer.FrameCallback? = null

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        if (level == ComponentCallbacks2.TRIM_MEMORY_RUNNING_CRITICAL) {
            Log.w("MainActivity", "Memory critical: level=$level")
        }
    }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val denied = permissions.filterValues { !it }.keys
        if (denied.isNotEmpty()) {
            Log.w("MainActivity", "Permissions denied: $denied — some features may not work")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val isDebug = (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
        if (isDebug) {
            StrictMode.setThreadPolicy(
                StrictMode.ThreadPolicy.Builder()
                    .detectAll()
                    .penaltyLog()
                    .build()
            )
            StrictMode.setVmPolicy(
                StrictMode.VmPolicy.Builder()
                    .detectLeakedClosableObjects()
                    .penaltyLog()
                    .build()
            )
        }
        setupFrameMonitor()

        // Build the permission list based on OS version
        val perms = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACTIVITY_RECOGNITION,
            Manifest.permission.POST_NOTIFICATIONS,
            Manifest.permission.FOREGROUND_SERVICE,
            Manifest.permission.FOREGROUND_SERVICE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= 33) {
            perms += Manifest.permission.NEARBY_WIFI_DEVICES
        }

        requestPermissionLauncher.launch(perms.toTypedArray())

        handleDeepLink(intent)

        setContent {
            AutoLifeApp(
                modifier = Modifier.semantics { testTagsAsResourceId = true },
                onServiceToggle = { shouldStart ->
                    val intent = Intent(this, AutoLifeService::class.java)
                    if (shouldStart) {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                            startForegroundService(intent)
                        } else {
                            startService(intent)
                        }
                    } else {
                        stopService(intent)
                    }
                },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent?) {
        val uri = intent?.data ?: return
        if (uri.scheme == "autolife" && uri.host == "run_analysis") {
            AnalysisRepository.requestRunAnalysis()
        }
    }

    private fun setupFrameMonitor() {
        val choreographer = Choreographer.getInstance()
        frameCallback = object : Choreographer.FrameCallback {
            private var lastFrameTimeNanos: Long = 0L
            override fun doFrame(frameTimeNanos: Long) {
                if (lastFrameTimeNanos != 0L) {
                    val diffMs = (frameTimeNanos - lastFrameTimeNanos) / 1_000_000
                    if (diffMs > 32) {
                        Log.w("FrameMonitor", "Long frame: ${diffMs}ms")
                    }
                }
                lastFrameTimeNanos = frameTimeNanos
                choreographer.postFrameCallback(this)
            }
        }
        choreographer.postFrameCallback(frameCallback!!)
    }

    override fun onDestroy() {
        super.onDestroy()
        frameCallback?.let { Choreographer.getInstance().removeFrameCallback(it) }
        frameCallback = null
    }
}
