package com.autolife.composeapp.ui

import com.autolife.shared.model.ApplyCalendarRequest
import com.autolife.shared.model.ProposedChange
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.platform.currentTimeZoneId
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
            val current = AnalysisRepository.result.value
            val resp = AutoLifeApi.applyCalendar(
                ApplyCalendarRequest(
                    changes = changes,
                    user_timezone = currentTimeZoneId(),
                    proposed_changes = current?.proposed_changes ?: emptyList(),
                    user_id = AnalysisRepository.userId,
                )
            )
            if (current != null) {
                val appliedChanges = changes.filter { requested ->
                    resp.applied.any { applied -> sameProposal(requested, applied) }
                }.let { matched ->
                    if (matched.isEmpty() && resp.applied.size == changes.size && resp.failed.isEmpty()) changes else matched
                }
                AnalysisRepository.setResult(
                    current.copy(
                        proposed_changes = current.proposed_changes.filter { it !in appliedChanges },
                    ),
                )
            }
            AnalysisRepository.clearProposals()
            val failedCount = resp.failed.size + resp.skipped.size
            val message = when {
                resp.applied.isNotEmpty() && failedCount == 0 ->
                    "Created ${resp.applied.size} event${if (resp.applied.size == 1) "" else "s"} in Google Calendar"
                resp.applied.isNotEmpty() ->
                    "Created ${resp.applied.size} in Google Calendar · failed $failedCount"
                else ->
                    "No events created in Google Calendar · failed $failedCount"
            }
            SnackbarBus.emit(message)
        } catch (e: Exception) {
            SnackbarBus.emit("Apply failed: ${e.message ?: "unknown error"}")
        } finally {
            _isApplying.value = false
        }
    }

    private fun sameProposal(requested: ProposedChange, applied: ProposedChange): Boolean {
        val requestedToken = requested.change_token
        if (!requestedToken.isNullOrBlank() && requestedToken == applied.change_token) return true
        val requestedTitle = requested.title?.trim()
        val appliedTitle = applied.title?.trim()
        if (requestedTitle.isNullOrBlank() || requestedTitle != appliedTitle) return false
        val appliedStart = applied.start_time
        return appliedStart.isNullOrBlank() || appliedStart == requested.start_time
    }

}
