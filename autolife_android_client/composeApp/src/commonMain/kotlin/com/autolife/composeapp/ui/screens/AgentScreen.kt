package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.ui.DateFormat
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.*
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.repository.AnalysisRepository
import io.ktor.client.plugins.HttpRequestTimeoutException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

class AgentViewModel : ViewModel() {
    private val repo = AnalysisRepository
    private var analysisJob: Job? = null
    var lastJournalCount by mutableStateOf(0)
        private set

    init {
        // Auto-trigger analysis when requested via deep link / intent
        viewModelScope.launch {
            repo.pendingRunAnalysis.collect { pending ->
                if (pending) {
                    repo.consumeRunAnalysis()
                    runAnalysis()
                }
            }
        }
    }

    fun runAnalysis() {
        analysisJob = viewModelScope.launch {
            repo.setLoading(true)
            repo.setError(null)
            try {
                val dbJournals = DatabaseRepository.getAllJournals().takeLast(10)
                if (dbJournals.isEmpty()) {
                    repo.setError("No journals found. Start the AutoLife service to collect data first.")
                    return@launch
                }
                lastJournalCount = dbJournals.size
                val apiJournals = dbJournals.mapIndexed { index, j ->
                    ApiJournalEntry(
                        id = j.id.toString(),
                        entry_number = index + 1,
                        created_at = DateFormat.dateTime(j.createdTimestamp),
                        period = "Auto-generated",
                        content = j.content,
                        timestamp = DateFormat.dateTime(j.createdTimestamp)
                    )
                }
                val response = AutoLifeApi.processJournals(
                    ProcessJournalsRequest(journals = apiJournals)
                )
                repo.setResult(response)
                repo.clearProposals()
            } catch (e: CancellationException) {
                throw e
            } catch (e: HttpRequestTimeoutException) {
                repo.setError("Request timed out — the server may still be initializing. Try again in a moment.")
            } catch (e: Exception) {
                val msg = e.message ?: e.toString()
                val isConnect = msg.contains("Connection refused", ignoreCase = true) ||
                    msg.contains("Failed to connect", ignoreCase = true) ||
                    msg.contains("Unable to resolve host", ignoreCase = true)
                if (isConnect) {
                    repo.setError(
                        "Cannot reach backend server.\n" +
                        "• Emulator: ensure the server is running on host port 8000\n" +
                        "• Physical device: set BACKEND_URL in local.properties"
                    )
                } else {
                    repo.setError("Analysis failed: $msg")
                }
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
        repo.setError("Cancelled by user")
    }
}

private enum class ExpandedTool { AUTOLIFE, KEMO, VECTORDB, CALENDAR, LAST_RESULT }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentScreen(viewModel: AgentViewModel = viewModel { AgentViewModel() }) {
    val result by AnalysisRepository.result.collectAsState()
    val isLoading by AnalysisRepository.loading.collectAsState()
    val error by AnalysisRepository.error.collectAsState()
    val lastRunMs by AnalysisRepository.lastRunMs.collectAsState()
    val memory by AnalysisRepository.memory.collectAsState()

    var expandedTool by remember { mutableStateOf<ExpandedTool?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Agent control card
        item {
            SurfaceCard {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "Life Agent",
                        style = MaterialTheme.typography.headlineMedium,
                    )
                    StatusPill(
                        text = if (isLoading) "Running" else if (result != null) "Ready" else "Idle",
                        color = if (isLoading) MaterialTheme.colorScheme.tertiary
                                else MaterialTheme.colorScheme.secondary,
                    )
                }
                Spacer(Modifier.height(8.dp))
                DataRow(
                    label = "Last Run",
                    value = lastRunMs?.let { DateFormat.time(it) } ?: "—",
                )
                DataRow(
                    label = "Journals Sent",
                    value = if (viewModel.lastJournalCount > 0) "${viewModel.lastJournalCount}" else "—",
                )
                Spacer(Modifier.height(12.dp))
                if (isLoading) {
                    Button(
                        onClick = { viewModel.cancelAnalysis() },
                        modifier = Modifier.fillMaxWidth().testTag("btn_cancel_analysis"),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error,
                        ),
                    ) {
                        Icon(Icons.Default.Stop, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Cancel Analysis")
                    }
                    Spacer(Modifier.height(8.dp))
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                } else {
                    Button(
                        onClick = { viewModel.runAnalysis() },
                        modifier = Modifier.fillMaxWidth().testTag("btn_run_analysis"),
                    ) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Run Analysis")
                    }
                }
                if (error != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        text = error!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }

        // Tools grid
        item {
            SectionHeader(title = "Tools", action = {
                Text(
                    text = "Tap to expand",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            })
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    LiveAutoLifeCard(
                        modifier = Modifier.weight(1f),
                        onClick = { expandedTool = ExpandedTool.AUTOLIFE },
                    )
                    ToolCard(
                        modifier = Modifier.weight(1f),
                        accentColor = AutoLifeSemantic.toolKEmo,
                        title = "K-Emo",
                        subtitle = "Mental State",
                        dataLines = listOf(
                            "PHQ-4" to (result?.mental_health?.estimated_phq4?.let { "$it/12" } ?: "—"),
                            "Risk" to (result?.mental_health?.risk_level?.replaceFirstChar { it.uppercase() } ?: "—"),
                        ),
                        status = if (result?.mental_health != null) "Ready" else "Idle",
                        onClick = { expandedTool = ExpandedTool.KEMO },
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    val vectorErr = result?.errors?.any {
                        it.contains("vector", ignoreCase = true) || it.contains("chroma", ignoreCase = true)
                    } == true
                    ToolCard(
                        modifier = Modifier.weight(1f),
                        accentColor = AutoLifeSemantic.toolVectorDB,
                        title = "VectorDB",
                        subtitle = "Wellness Research",
                        dataLines = listOf(
                            "Status" to if (result != null && !vectorErr) "OK" else "—",
                            "Top-K" to "5",
                        ),
                        status = if (vectorErr) "Error" else if (result != null) "Ready" else "Idle",
                        onClick = { expandedTool = ExpandedTool.VECTORDB },
                    )
                    ToolCard(
                        modifier = Modifier.weight(1f),
                        accentColor = AutoLifeSemantic.toolCalendar,
                        title = "Calendar",
                        subtitle = "Events & Tasks",
                        dataLines = listOf(
                            "Events" to (result?.calendar_summary?.event_count?.toString() ?: "—"),
                            "Tasks" to (result?.calendar_summary?.task_count?.toString() ?: "—"),
                        ),
                        status = if (result?.calendar_summary?.event_count != null) "Ready" else "Idle",
                        onClick = { expandedTool = ExpandedTool.CALENDAR },
                    )
                }
            }
        }

        // Memory section
        item {
            SectionHeader(title = "Memory")
            SurfaceCard {
                DataRow(
                    label = "Preferences",
                    value = if (memory != null) "Loaded · ${memory!!.preferences.goals.size} goals" else "—",
                )
                DataRow(
                    label = "Health History",
                    value = if (memory != null)
                        "${memory!!.mental_health.history.size} entries · ${memory!!.mental_health.trend.replaceFirstChar { it.uppercase() }}"
                    else "—",
                )
            }
        }

        // Last result summary
        if (result != null) {
            item {
                SectionHeader(title = "Last Result", action = {
                    TextButton(onClick = { expandedTool = ExpandedTool.LAST_RESULT }) {
                        Text("Details")
                    }
                })
                val mh = result!!.mental_health
                val rc = AutoLifeSemantic.riskColor(mh?.risk_level)
                SurfaceCard(modifier = Modifier.clickable { expandedTool = ExpandedTool.LAST_RESULT }) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "${mh?.estimated_phq4 ?: "—"}",
                                style = MaterialTheme.typography.titleLarge,
                                color = rc,
                                fontWeight = FontWeight.Bold,
                            )
                            Text("PHQ-4", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "${result!!.recommendations.size}",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Text("Recs", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "${result!!.proposed_changes.size}",
                                style = MaterialTheme.typography.titleLarge,
                                color = MaterialTheme.colorScheme.primary,
                                fontWeight = FontWeight.Bold,
                            )
                            Text("Changes", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    if (result!!.errors.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = "${result!!.errors.size} error(s)",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
        }
    }

    // Tool detail bottom sheet
    expandedTool?.let { tool ->
        ToolDetailSheet(tool = tool, result = result, onDismiss = { expandedTool = null })
    }
}

// --- Tool Card ---

@Composable
private fun ToolCard(
    modifier: Modifier,
    accentColor: Color,
    title: String,
    subtitle: String,
    dataLines: List<Pair<String, String>>,
    status: String,
    onClick: () -> Unit,
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    shape = RoundedCornerShape(6.dp),
                    color = accentColor.copy(alpha = 0.15f),
                    modifier = Modifier.size(28.dp),
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            text = title.first().toString(),
                            style = MaterialTheme.typography.labelLarge,
                            color = accentColor,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
                Spacer(Modifier.width(8.dp))
                Column {
                    Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(subtitle, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Spacer(Modifier.height(8.dp))
            dataLines.forEach { (lbl, v) ->
                DataRow(label = lbl, value = v)
            }
            Spacer(Modifier.height(6.dp))
            StatusPill(
                text = status,
                color = when (status) {
                    "Ready", "Active" -> MaterialTheme.colorScheme.secondary
                    "Error" -> MaterialTheme.colorScheme.error
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
    }
}

@Composable
private fun LiveAutoLifeCard(modifier: Modifier, onClick: () -> Unit) {
    val motionState by PlatformStateProvider.motionState.collectAsState()
    ToolCard(
        modifier = modifier,
        accentColor = AutoLifeSemantic.toolAutoLife,
        title = "AutoLife",
        subtitle = "Motion & Location",
        dataLines = listOf(
            "Activity" to motionState.detectedClass,
            "Accel" to "${DateFormat.fmtFloat2(motionState.acceleration)} m/s²",
        ),
        status = "Active",
        onClick = onClick,
    )
}

// --- Tool Detail Bottom Sheet ---

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ToolDetailSheet(
    tool: ExpandedTool,
    result: ProcessJournalsResponse?,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
    ) {
        val (sheetTitle, accentColor) = when (tool) {
            ExpandedTool.AUTOLIFE -> "AutoLife — Motion & Location" to AutoLifeSemantic.toolAutoLife
            ExpandedTool.KEMO -> "K-Emo — Mental State" to AutoLifeSemantic.toolKEmo
            ExpandedTool.VECTORDB -> "VectorDB — Wellness Research" to AutoLifeSemantic.toolVectorDB
            ExpandedTool.CALENDAR -> "Calendar — Events & Tasks" to AutoLifeSemantic.toolCalendar
            ExpandedTool.LAST_RESULT -> "Full Analysis Result" to AutoLifeSemantic.riskColor(result?.mental_health?.risk_level)
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = sheetTitle,
                    style = MaterialTheme.typography.titleLarge,
                    color = accentColor,
                )
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = "Close")
                }
            }
            HorizontalDivider()

            when (tool) {
                ExpandedTool.AUTOLIFE -> AutoLifeDetail()
                ExpandedTool.KEMO -> KemoDetail(result)
                ExpandedTool.VECTORDB -> VectorDBDetail(result)
                ExpandedTool.CALENDAR -> CalendarDetail(result)
                ExpandedTool.LAST_RESULT -> LastResultDetail(result)
            }
        }
    }
}

@Composable
private fun AutoLifeDetail() {
    val motionState by PlatformStateProvider.motionState.collectAsState()
    SurfaceCard {
        SectionHeader(title = "Live Sensor Data")
        DataRow("Activity", motionState.detectedClass)
        DataRow("Acceleration", "${DateFormat.fmtFloat3(motionState.acceleration)} m/s²")
        DataRow("Status", "Active — collecting continuously")
    }
    SurfaceCard {
        SectionHeader(title = "Description")
        Text(
            "AutoLife reads motion sensors and location data to generate journal entries. " +
            "It classifies activity (walking, stationary, vehicle) and records GPS coordinates for context fusion.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun KemoDetail(result: ProcessJournalsResponse?) {
    val mh = result?.mental_health
    SurfaceCard {
        SectionHeader(title = "PHQ-4 Assessment")
        DataRow("Score", mh?.estimated_phq4?.let { "$it / 12" } ?: "— (run analysis first)")
        DataRow("Risk Level", mh?.risk_level?.replaceFirstChar { it.uppercase() } ?: "—")
    }
    if (mh != null) {
        if (mh.key_concerns.isNotEmpty()) {
            SurfaceCard {
                SectionHeader(title = "Key Concerns")
                mh.key_concerns.forEach { Text("  •  $it", style = MaterialTheme.typography.bodyMedium) }
            }
        }
        if (mh.positive_indicators.isNotEmpty()) {
            SurfaceCard {
                SectionHeader(title = "Positive Indicators")
                mh.positive_indicators.forEach {
                    Text("  •  $it", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary)
                }
            }
        }
    }
    SurfaceCard {
        SectionHeader(title = "Scoring Guide")
        DataRow("0–2", "Minimal — healthy, normal")
        DataRow("3–5", "Mild — some stress indicators")
        DataRow("6–8", "Moderate — intervention recommended")
        DataRow("9–12", "Severe — immediate support needed")
    }
}

@Composable
private fun VectorDBDetail(result: ProcessJournalsResponse?) {
    val hasError = result?.errors?.any {
        it.contains("vector", ignoreCase = true) || it.contains("chroma", ignoreCase = true)
    } == true
    SurfaceCard {
        SectionHeader(title = "Status")
        DataRow("Backend", if (result != null && !hasError) "Connected" else if (hasError) "Error" else "—")
        DataRow("Retrieval K", "5")
        DataRow("Embedding Model", "gemini-embedding-2")
    }
    SurfaceCard {
        SectionHeader(title = "Description")
        Text(
            "VectorDB stores embeddings of peer-reviewed wellness research. " +
            "It retrieves the top-k most relevant interventions based on your PHQ-4 score and journal summary, " +
            "providing evidence-based grounding for recommendations.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    if (hasError) {
        SurfaceCard {
            Text(
                text = result?.errors?.firstOrNull { it.contains("vector", ignoreCase = true) } ?: "VectorDB unavailable",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
        }
    }
}

@Composable
private fun CalendarDetail(result: ProcessJournalsResponse?) {
    val summary = result?.calendar_summary
    SurfaceCard {
        SectionHeader(title = "Summary")
        DataRow("Events", summary?.event_count?.toString() ?: "— (run analysis first)")
        DataRow("Tasks", summary?.task_count?.toString() ?: "—")
        DataRow("Total Scheduled", summary?.total_hours?.let { "${DateFormat.fmtFloat1(it)}h" } ?: "—")
    }
    val events = summary?.events
    if (!events.isNullOrEmpty()) {
        SurfaceCard {
            SectionHeader(title = "Events This Week")
            events.take(15).forEach { ev ->
                DataRow(ev.title.ifBlank { "Untitled" }, ev.start.replace("T", " ").take(16))
            }
        }
    }
    val tasks = summary?.tasks
    if (!tasks.isNullOrEmpty()) {
        SurfaceCard {
            SectionHeader(title = "Pending Tasks")
            tasks.take(10).forEach { task ->
                DataRow(task.title.ifBlank { "Untitled" }, task.due ?: "No due date")
            }
        }
    }
}

@Composable
private fun LastResultDetail(result: ProcessJournalsResponse?) {
    if (result == null) {
        Text("No result yet — run analysis first.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        return
    }
    val mh = result.mental_health
    SurfaceCard {
        SectionHeader(title = "Mental Health")
        DataRow("PHQ-4", mh?.estimated_phq4?.let { "$it / 12" } ?: "—")
        DataRow("Risk Level", mh?.risk_level?.replaceFirstChar { it.uppercase() } ?: "—")
        if (!result.journal_summary.isNullOrBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(result.journal_summary!!, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
    if (result.recommendations.isNotEmpty()) {
        SurfaceCard {
            SectionHeader(title = "Recommendations (${result.recommendations.size})")
            result.recommendations.forEachIndexed { i, rec ->
                if (i > 0) Spacer(Modifier.height(6.dp))
                Row {
                    StatusPill(text = rec.category.replaceFirstChar { it.uppercase() }, color = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(rec.action, style = MaterialTheme.typography.bodyMedium)
                        val meta = listOfNotNull(
                            rec.when_to_do?.let { "When: $it" },
                            rec.priority?.let { "Priority: $it" },
                        ).joinToString(" · ")
                        if (meta.isNotBlank()) {
                            Text(meta, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
    if (result.proposed_changes.isNotEmpty()) {
        SurfaceCard {
            SectionHeader(title = "Proposed Changes (${result.proposed_changes.size})")
            result.proposed_changes.forEach { change ->
                DataRow(
                    label = change.title ?: "Untitled",
                    value = change.start_time?.replace("T", " ")?.take(16) ?: "",
                )
            }
        }
    }
    if (result.errors.isNotEmpty()) {
        SurfaceCard {
            SectionHeader(title = "Errors (${result.errors.size})")
            result.errors.forEach {
                Text("  •  $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}
