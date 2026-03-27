package com.google.mediapipe.examples.llminference.ui

import android.app.Application
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mediapipe.examples.llminference.AutoLifeApp
import com.google.mediapipe.examples.llminference.data.AnalysisRepository
import com.google.mediapipe.examples.llminference.data.DebugRepository
import com.google.mediapipe.examples.llminference.network.*
import com.google.mediapipe.examples.llminference.ui.theme.*
import com.google.mediapipe.examples.llminference.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.text.SimpleDateFormat
import java.util.*

// ── ViewModel ─────────────────────────────────────────────────

class AgentViewModel(application: Application) : AndroidViewModel(application) {
    private val dao = (application as AutoLifeApp).database.logDao()
    private val repo = AnalysisRepository
    private var analysisJob: Job? = null

    var lastJournalCount by mutableStateOf(0)
        private set

    fun runAnalysis() {
        analysisJob = viewModelScope.launch {
            repo.setLoading(true)
            repo.setError(null)
            try {
                val dbJournals = dao.getAllJournals().takeLast(10)
                if (dbJournals.isEmpty()) {
                    repo.setError("no_journals: Start AutoLife service to collect data first.")
                    return@launch
                }
                lastJournalCount = dbJournals.size
                val sdf = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                val apiJournals = dbJournals.mapIndexed { index, j ->
                    ApiJournalEntry(
                        id = j.id.toString(),
                        entry_number = index + 1,
                        created_at = sdf.format(Date(j.createdTimestamp)),
                        period = "Auto-generated",
                        content = j.content,
                        timestamp = sdf.format(Date(j.createdTimestamp))
                    )
                }
                val response = BackendApiClient.apiService.processJournals(
                    ProcessJournalsRequest(journals = apiJournals)
                )
                repo.setResult(response)
                repo.selectedProposals.clear()
            } catch (e: CancellationException) {
                throw e
            } catch (e: ConnectException) {
                repo.setError(
                    "Cannot reach backend at ${BuildConfig.BACKEND_URL}\n" +
                    "• Emulator: ensure server is running on host port 8000\n" +
                    "• Physical device: set BACKEND_URL=http://<your-mac-ip>:8000 in local.properties"
                )
            } catch (e: SocketTimeoutException) {
                repo.setError("Request timed out — server may still be initializing. Try again in a moment.")
            } catch (e: Exception) {
                repo.setError("err: ${e.message}")
            } finally {
                repo.setLoading(false)
                analysisJob = null
            }
        }
    }

    fun cancelAnalysis() {
        analysisJob?.cancel()
        analysisJob = null
        repo.setLoading(false)
        repo.setError("cancelled by user")
    }
}

// ── Screen ────────────────────────────────────────────────────

@Composable
fun AgentScreen(viewModel: AgentViewModel = viewModel()) {
    val result    by AnalysisRepository.result.collectAsStateWithLifecycle()
    val isLoading by AnalysisRepository.loading.collectAsStateWithLifecycle()
    val error     by AnalysisRepository.error.collectAsStateWithLifecycle()
    val lastRunMs by AnalysisRepository.lastRunMs.collectAsStateWithLifecycle()
    val memory    by AnalysisRepository.memory.collectAsStateWithLifecycle()

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(horizontal = 12.dp),
        contentPadding = PaddingValues(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // ── Agent card ───────────────────────────────────────
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(2.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF0E1A2E)),
                border = BorderStroke(1.dp, AgentBlue)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "LLM SCHEDULER AGENT",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        StatusBadge(
                            if (isLoading) "RUNNING" else if (result != null) "READY" else "IDLE",
                            color = if (isLoading) TerminalAmber else TerminalGreen
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    MonoRow(
                        "last_run",
                        lastRunMs?.let {
                            SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date(it))
                        } ?: "─",
                        valueColor = DarkOnSurfaceDim
                    )
                    MonoRow("user_id", "default", valueColor = DarkOnSurfaceDim)
                    MonoRow(
                        "journals_sent",
                        if (viewModel.lastJournalCount > 0) "${viewModel.lastJournalCount}" else "─",
                        valueColor = DarkOnSurfaceDim
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    if (isLoading) {
                        OutlinedButton(
                            onClick = { viewModel.cancelAnalysis() },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(2.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = TerminalRed),
                            border = BorderStroke(1.dp, TerminalRed)
                        ) {
                            Text("■  CANCEL ANALYSIS", style = MaterialTheme.typography.labelLarge)
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        LinearProgressIndicator(
                            modifier = Modifier.fillMaxWidth(),
                            color = TerminalGreen,
                            trackColor = DarkBorder
                        )
                    } else {
                        OutlinedButton(
                            onClick = { viewModel.runAnalysis() },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(2.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = TerminalGreen),
                            border = BorderStroke(1.dp, TerminalGreen)
                        ) {
                            Text("▶  RUN ANALYSIS", style = MaterialTheme.typography.labelLarge)
                        }
                    }
                    if (error != null) {
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            error!!,
                            style = MaterialTheme.typography.labelMedium,
                            color = TerminalRed
                        )
                    }
                }
            }
        }

        // ── Tools grid ───────────────────────────────────────
        item {
            SectionHeader("TOOLS")
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    LiveAutoLifeCard(modifier = Modifier.weight(1f))
                    ToolCard(
                        modifier = Modifier.weight(1f),
                        accentColor = ToolKEmo,
                        title = "K-Emo Phone",
                        subtitle = "Mental State",
                        dataLines = listOf(
                            "phq4"  to (result?.mental_health?.estimated_phq4?.let { "$it/12" } ?: "─"),
                            "risk"  to (result?.mental_health?.risk_level?.uppercase() ?: "─")
                        ),
                        output = "→ PHQ Score",
                        status = if (result?.mental_health != null) "READY" else "IDLE"
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    val vectorErr = result?.errors?.any {
                        it.contains("vector", ignoreCase = true) ||
                        it.contains("chroma", ignoreCase = true)
                    } == true
                    ToolCard(
                        modifier = Modifier.weight(1f),
                        accentColor = ToolVectorDB,
                        title = "VectorDB",
                        subtitle = "Wellness Research",
                        dataLines = listOf(
                            "status" to if (result != null && !vectorErr) "ok" else "─",
                            "top_k"  to "5"
                        ),
                        output = "→ Top K Concept",
                        status = if (vectorErr) "ERR" else if (result != null) "READY" else "IDLE"
                    )
                    @Suppress("UNCHECKED_CAST")
                    val eventCount = (result?.calendar_summary?.get("event_count") as? Double)?.toInt()
                    val taskCount  = (result?.calendar_summary?.get("task_count")  as? Double)?.toInt()
                    ToolCard(
                        modifier = Modifier.weight(1f),
                        accentColor = ToolCalendar,
                        title = "Calendar API",
                        subtitle = "Events & Tasks",
                        dataLines = listOf(
                            "events" to (eventCount?.toString() ?: "─"),
                            "tasks"  to (taskCount?.toString()  ?: "─")
                        ),
                        output = "→ Schedule",
                        status = if (eventCount != null) "READY" else "IDLE"
                    )
                }
            }
        }

        // ── Memory section ───────────────────────────────────
        item {
            SectionHeader("MEMORY")
            TerminalCard(accentColor = TerminalGreen) {
                MonoRow(
                    "user_prefs",
                    if (memory != null) "[loaded]  goals: ${memory!!.preferences.goals.size}" else "─"
                )
                MonoRow(
                    "health_hist",
                    if (memory != null)
                        "[${memory!!.mental_health.history.size} entries]  trend: ${memory!!.mental_health.trend.uppercase()}"
                    else "─"
                )
            }
        }

        // ── Last result summary ──────────────────────────────
        if (result != null) {
            item {
                SectionHeader("LAST RESULT")
                TerminalCard(accentColor = riskColor(result!!.mental_health?.risk_level ?: "")) {
                    val mh = result!!.mental_health
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Text(
                            "phq4: ${mh?.estimated_phq4 ?: "─"}/12",
                            style = MaterialTheme.typography.labelLarge,
                            color = riskColor(mh?.risk_level ?: "")
                        )
                        Text(
                            "risk: [${mh?.risk_level?.uppercase() ?: "─"}]",
                            style = MaterialTheme.typography.labelLarge,
                            color = riskColor(mh?.risk_level ?: "")
                        )
                        Text(
                            "recs: ${result!!.recommendations.size}",
                            style = MaterialTheme.typography.labelLarge,
                            color = DarkOnSurface
                        )
                        Text(
                            "Δcal: ${result!!.proposed_changes.size}",
                            style = MaterialTheme.typography.labelLarge,
                            color = TerminalCyan
                        )
                    }
                    val errCount = result!!.errors.size
                    if (errCount > 0) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "errors: $errCount  (see Health tab for details)",
                            style = MaterialTheme.typography.labelSmall,
                            color = TerminalRed
                        )
                    }
                }
            }
        }
    }
}

// ── Live AutoLife card (isolates motionStats recomposition) ───

@Composable
private fun LiveAutoLifeCard(modifier: Modifier) {
    val motionStats by DebugRepository.motionStats.collectAsStateWithLifecycle()
    ToolCard(
        modifier    = modifier,
        accentColor = ToolAutoLife,
        title       = "AutoLife",
        subtitle    = "Motion & Location",
        dataLines   = listOf(
            "class" to motionStats.detectedClass,
            "accel" to "${"%.2f".format(motionStats.acceleration)} m/s²"
        ),
        output = "→ Daily Journal",
        status = "ACTIVE"
    )
}

// ── Tool Card ─────────────────────────────────────────────────

@Composable
private fun ToolCard(
    modifier: Modifier,
    accentColor: Color,
    title: String,
    subtitle: String,
    dataLines: List<Pair<String, String>>,
    output: String,
    status: String
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, DarkBorder)
    ) {
        Row(modifier = Modifier.height(IntrinsicSize.Min)) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .fillMaxHeight()
                    .background(accentColor)
            )
            Column(modifier = Modifier.padding(10.dp)) {
                Text(
                    title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = DarkOnSurfaceDim
                )
                Spacer(modifier = Modifier.height(6.dp))
                dataLines.forEach { (lbl, v) ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            "$lbl:",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim
                        )
                        Text(
                            v,
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurface
                        )
                    }
                }
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        output,
                        style = MaterialTheme.typography.labelSmall,
                        color = accentColor
                    )
                    Text(
                        "[$status]",
                        style = MaterialTheme.typography.labelSmall,
                        color = when (status) {
                            "ACTIVE", "READY" -> TerminalGreen
                            "ERR"             -> TerminalRed
                            else              -> DarkOnSurfaceDim
                        }
                    )
                }
            }
        }
    }
}
