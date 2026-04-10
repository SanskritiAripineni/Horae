package com.autolife.composeapp.platform

/**
 * Bridge object that allows Swift code to register callbacks that Kotlin iosMain code
 * can invoke. Needed because Kotlin iosMain cannot call Swift classes directly.
 */
object IOSServiceBridge {
    var onServiceToggle: ((Boolean) -> Unit)? = null
}
