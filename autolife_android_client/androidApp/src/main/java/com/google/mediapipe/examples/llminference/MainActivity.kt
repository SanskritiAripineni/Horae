package com.google.mediapipe.examples.llminference

import android.os.Build
import android.Manifest
import android.content.ComponentCallbacks2
import android.graphics.Color
import android.os.Bundle
import android.os.StrictMode
import android.util.Log
import android.view.View
import android.view.Choreographer
import android.widget.Toast
import androidx.activity.ComponentActivity
import android.content.Intent
import android.content.pm.PackageManager
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
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
            com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
        } else {
            toggleAutoLifeService(true)
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
        configureSystemBars()

        handleDeepLink(intent)

        setContent {
            AutoLifeApp(
                modifier = Modifier.semantics { testTagsAsResourceId = true },
                onServiceToggle = { shouldStart ->
                    toggleAutoLifeService(shouldStart)
                },
                onDecline = { finishAffinity() },
                onConsentReady = { requestMissingRuntimePermissions() },
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

    private fun configureSystemBars() {
        window.statusBarColor = Color.rgb(251, 252, 248)
        window.navigationBarColor = Color.rgb(251, 252, 248)
        var flags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            flags = flags or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        }
        window.decorView.systemUiVisibility = flags
    }

    private fun runtimePermissions(): Array<String> {
        val perms = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            perms += Manifest.permission.ACTIVITY_RECOGNITION
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms += Manifest.permission.POST_NOTIFICATIONS
            perms += Manifest.permission.NEARBY_WIFI_DEVICES
        }
        return perms.toTypedArray()
    }

    private fun missingRuntimePermissions(): Array<String> =
        runtimePermissions().filter { permission ->
            ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED
        }.toTypedArray()

    private fun requestMissingRuntimePermissions() {
        val missing = missingRuntimePermissions()
        if (missing.isNotEmpty()) {
            requestPermissionLauncher.launch(missing)
        } else {
            toggleAutoLifeService(true)
        }
    }

    private fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun toggleAutoLifeService(shouldStart: Boolean) {
        val intent = Intent(this, AutoLifeService::class.java)
        if (!shouldStart) {
            stopService(intent)
            return
        }

        if (!hasLocationPermission()) {
            requestMissingRuntimePermissions()
            Toast.makeText(
                this,
                "Location permission is required before AutoLife can record in the background.",
                Toast.LENGTH_LONG,
            ).show()
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        frameCallback?.let { Choreographer.getInstance().removeFrameCallback(it) }
        frameCallback = null
    }
}
