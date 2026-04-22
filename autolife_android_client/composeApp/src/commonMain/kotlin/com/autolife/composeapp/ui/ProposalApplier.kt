package com.autolife.composeapp.ui

import com.autolife.shared.model.ApplyCalendarRequest
import com.autolife.shared.model.ProposedChange
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.repository.AnalysisRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Shared coroutine helper both AgentScreen (one-tap apply) and ScheduleScreen use to apply
 * proposed calendar changes. Keeps a single in-flight flag so the UI can disable buttons anywhere.
 */
object ProposalApplier {
    private val _isApplying = MutableStateFlow(false)
    val isApplying: StateFlow<Boolean> = _isApplying.asStateFlow()

    /** Apply the given proposals and emit a snackbar message describing the outcome. */
    suspend fun apply(changes: List<ProposedChange>) {
        if (changes.isEmpty() || _isApplying.value) return
        _isApplying.value = true
        try {
            val resp = AutoLifeApi.applyCalendar(ApplyCalendarRequest(changes = changes))
            val current = AnalysisRepository.result.value
            if (current != null) {
                AnalysisRepository.setResult(
                    current.copy(
                        proposed_changes = current.proposed_changes.filter { it !in changes },
                    ),
                )
            }
            AnalysisRepository.clearProposals()
            SnackbarBus.emit("Applied ${resp.applied.size} · failed ${resp.failed.size}")
        } catch (e: Exception) {
            SnackbarBus.emit("Apply failed: ${e.message ?: "unknown error"}")
        } finally {
            _isApplying.value = false
        }
    }
}
