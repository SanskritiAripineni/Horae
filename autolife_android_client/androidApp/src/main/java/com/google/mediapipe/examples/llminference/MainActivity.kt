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
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import com.autolife.composeapp.AutoLifeApp
import com.autolife.shared.repository.AnalysisRepository

class MainActivity : ComponentActivity() {

    private enum class PermissionRequest { Core, Optional }

    private var frameCallback: Choreographer.FrameCallback? = null
    private var pendingPermissionRequest = PermissionRequest.Core

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
        when (pendingPermissionRequest) {
            PermissionRequest.Core -> {
                if (hasCoreCollectionPermissions()) {
                    if (denied.isNotEmpty()) {
                        Log.w("MainActivity", "Non-core permissions denied during core request: $denied")
                    }
                    toggleAutoLifeService(true)
                    requestMissingOptionalRuntimePermissions()
                } else {
                    Log.w("MainActivity", "Core permissions denied: $denied")
                    com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
                    Toast.makeText(
                        this,
                        "Location and motion permissions are required before AutoLife can record in the background.",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }
            PermissionRequest.Optional -> {
                if (denied.isNotEmpty()) {
                    Log.w("MainActivity", "Optional permissions denied: $denied")
                    Toast.makeText(
                        this,
                        "Collecting with limited coverage: missing ${denied.joinToString { PermissionPolicy.coverageLabel(it) }}.",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }
        }
    }

    @OptIn(ExperimentalComposeUiApi::class)
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

    private fun missingRuntimePermissions(permissions: Array<String>): Array<String> =
        permissions.filter { permission ->
            ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED
        }.toTypedArray()

    private fun requestMissingRuntimePermissions() {
        val missing = missingRuntimePermissions(PermissionPolicy.requiredRuntimePermissions())
        if (missing.isNotEmpty()) {
            pendingPermissionRequest = PermissionRequest.Core
            requestPermissionLauncher.launch(missing)
        } else {
            toggleAutoLifeService(true)
            requestMissingOptionalRuntimePermissions()
        }
    }

    private fun requestMissingOptionalRuntimePermissions() {
        val missing = missingRuntimePermissions(PermissionPolicy.optionalRuntimePermissions())
        if (missing.isNotEmpty()) {
            pendingPermissionRequest = PermissionRequest.Optional
            requestPermissionLauncher.launch(missing)
        }
    }

    private fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun hasActivityRecognitionPermission(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACTIVITY_RECOGNITION) == PackageManager.PERMISSION_GRANTED

    private fun hasCoreCollectionPermissions(): Boolean =
        hasLocationPermission() && hasActivityRecognitionPermission()

    private fun toggleAutoLifeService(shouldStart: Boolean) {
        val intent = Intent(this, AutoLifeService::class.java)
        if (!shouldStart) {
            stopService(intent)
            com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
            return
        }

        if (!hasCoreCollectionPermissions()) {
            requestMissingRuntimePermissions()
            Toast.makeText(
                this,
                "Location and motion permissions are required before AutoLife can record in the background.",
                Toast.LENGTH_LONG,
            ).show()
            return
        }

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        } catch (e: IllegalStateException) {
            Log.w("MainActivity", "Unable to start AutoLife foreground service", e)
            com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
            Toast.makeText(
                this,
                "AutoLife could not start background collection from the current app state.",
                Toast.LENGTH_LONG,
            ).show()
        } catch (e: SecurityException) {
            Log.w("MainActivity", "Unable to start AutoLife foreground service without required permission", e)
            com.google.mediapipe.examples.llminference.data.DebugRepository.setServiceRunning(false)
            Toast.makeText(
                this,
                "AutoLife needs background collection permissions before it can start.",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        frameCallback?.let { Choreographer.getInstance().removeFrameCallback(it) }
        frameCallback = null
    }
}
