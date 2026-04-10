package com.autolife.shared.platform

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Cancellable handle returned to Swift callers so they can stop collection.
 */
class Cancellable(private val job: Job) {
    fun cancel() { job.cancel() }
}

/**
 * Helper that Swift code can call to collect a Kotlin [Flow] via callbacks.
 * Avoids needing Swift to deal with Kotlin coroutines / suspend functions directly.
 */
object FlowHelper {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    /**
     * Collect a [StateFlow] and call [onEach] for every emission (including the current value).
     * Returns a [Cancellable] that Swift should cancel when the view disappears.
     */
    fun <T> collectStateFlow(
        flow: StateFlow<T>,
        onEach: (T) -> Unit
    ): Cancellable {
        val job = scope.launch {
            flow.collect { value -> onEach(value) }
        }
        return Cancellable(job)
    }

    /**
     * Collect a regular [Flow] and call [onEach] for every emission.
     * Returns a [Cancellable] that Swift should cancel when the view disappears.
     */
    fun <T> collectFlow(
        flow: Flow<T>,
        onEach: (T) -> Unit
    ): Cancellable {
        val job = scope.launch {
            flow.collect { value -> onEach(value) }
        }
        return Cancellable(job)
    }
}
