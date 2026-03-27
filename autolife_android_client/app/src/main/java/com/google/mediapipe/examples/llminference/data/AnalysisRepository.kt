package com.google.mediapipe.examples.llminference.data

import androidx.compose.runtime.mutableStateListOf
import com.google.mediapipe.examples.llminference.network.ProcessJournalsResponse
import com.google.mediapipe.examples.llminference.network.UserMemoryData
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Singleton repository for the LLM Scheduler Agent analysis state.
 * All screens observe from here — avoids duplicate API calls and prop drilling.
 * Mirrors the DebugRepository pattern established in this project.
 */
object AnalysisRepository {

    private val _result  = MutableStateFlow<ProcessJournalsResponse?>(null)
    private val _loading = MutableStateFlow(false)
    private val _error   = MutableStateFlow<String?>(null)
    private val _memory  = MutableStateFlow<UserMemoryData?>(null)
    private val _lastRunMs = MutableStateFlow<Long?>(null)

    val result:    StateFlow<ProcessJournalsResponse?> = _result.asStateFlow()
    val loading:   StateFlow<Boolean>                   = _loading.asStateFlow()
    val error:     StateFlow<String?>                   = _error.asStateFlow()
    val memory:    StateFlow<UserMemoryData?>            = _memory.asStateFlow()
    val lastRunMs: StateFlow<Long?>                     = _lastRunMs.asStateFlow()

    /** Calendar proposals selected by user on ScheduleScreen for batch-apply. */
    val selectedProposals = mutableStateListOf<Map<String, Any>>()

    fun setResult(r: ProcessJournalsResponse?) {
        _result.value = r
        if (r != null) _lastRunMs.value = System.currentTimeMillis()
    }

    fun setLoading(v: Boolean) { _loading.value = v }
    fun setError(e: String?)   { _error.value = e }
    fun setMemory(m: UserMemoryData?) { _memory.value = m }
}
