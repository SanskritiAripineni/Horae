package com.autolife.composeapp.ui

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * App-wide ephemeral message bus for Snackbar feedback.
 * Screens emit; AutoLifeNavHost's SnackbarHost consumes. Survives navigation between tabs.
 */
object SnackbarBus {
    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    suspend fun emit(message: String) {
        _messages.emit(message)
    }

    fun tryEmit(message: String) {
        _messages.tryEmit(message)
    }
}
