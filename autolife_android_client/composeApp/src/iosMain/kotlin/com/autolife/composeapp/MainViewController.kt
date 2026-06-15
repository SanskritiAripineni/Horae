package com.autolife.composeapp

import androidx.compose.ui.window.ComposeUIViewController
import com.autolife.composeapp.platform.IOSServiceBridge

fun MainViewController() = ComposeUIViewController {
    AutoLifeApp(
        onServiceToggle = { shouldStart ->
            IOSServiceBridge.onServiceToggle?.invoke(shouldStart)
        },
        onConsentReady = {
            IOSServiceBridge.onServiceToggle?.invoke(true)
        },
        onDecline = {
            IOSServiceBridge.onServiceToggle?.invoke(false)
        },
    )
}
