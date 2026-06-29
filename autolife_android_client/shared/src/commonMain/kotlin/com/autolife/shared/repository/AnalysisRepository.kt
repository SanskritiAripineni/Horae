package com.autolife.shared.repository

import com.autolife.shared.model.ProcessJournalsResponse
import com.autolife.shared.model.ProposedChange
import com.autolife.shared.model.UserMemoryData
import com.autolife.shared.platform.currentTimeMillis
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Cross-platform singleton repository for the LLM Scheduler Agent analysis state.
 * All screens observe from here — avoids duplicate API calls and prop drilling.
 */
object AnalysisRepository {

    private val _result = MutableStateFlow<ProcessJournalsResponse?>(null)
    private val _loading = MutableStateFlow(false)
    private val _error = MutableStateFlow<String?>(null)
    private val _memory = MutableStateFlow<UserMemoryData?>(null)
    private val _lastRunMs = MutableStateFlow<Long?>(null)
    private val _selectedProposals = MutableStateFlow<List<ProposedChange>>(emptyList())

    val result: StateFlow<ProcessJournalsResponse?> = _result.asStateFlow()
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    val error: StateFlow<String?> = _error.asStateFlow()
    val memory: StateFlow<UserMemoryData?> = _memory.asStateFlow()
    val lastRunMs: StateFlow<Long?> = _lastRunMs.asStateFlow()
    val selectedProposals: StateFlow<List<ProposedChange>> = _selectedProposals.asStateFlow()

    var userId: String = "default"

    fun setResult(r: ProcessJournalsResponse?) {
        _result.value = r
        if (r != null) _lastRunMs.value = currentTimeMillis()
    }

    fun setLoading(v: Boolean) { _loading.value = v }
    fun setError(e: String?) { _error.value = e }
    fun setMemory(m: UserMemoryData?) { _memory.value = m }

    fun addProposal(p: ProposedChange) {
        _selectedProposals.value = _selectedProposals.value + p
    }

    fun removeProposal(p: ProposedChange) {
        _selectedProposals.value = _selectedProposals.value - p
    }

    fun clearProposals() {
        _selectedProposals.value = emptyList()
    }

    fun getSelectedProposalsList(): List<ProposedChange> = _selectedProposals.value

    /** Set by platform layer (e.g. deep link) to request analysis on next composition. */
    private val _pendingRunAnalysis = MutableStateFlow(false)
    val pendingRunAnalysis: StateFlow<Boolean> = _pendingRunAnalysis.asStateFlow()
    fun requestRunAnalysis() { _pendingRunAnalysis.value = true }
    fun consumeRunAnalysis() { _pendingRunAnalysis.value = false }
}
