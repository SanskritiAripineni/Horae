package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.platform.getBehavioralMarkers
import com.autolife.composeapp.ui.DateFormat
import com.autolife.composeapp.ui.ProposalApplier
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.*
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.repository.AnalysisRepository
import io.ktor.client.plugins.HttpRequestTimeoutException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.IO
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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
                val dbJournals = withContext(Dispatchers.IO) {
                    DatabaseRepository.getAllJournals().takeLast(10)
                }
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
                val rawDays = getBehavioralMarkers(14).takeIf { it.isNotEmpty() }
                val response = AutoLifeApi.processJournals(
                    ProcessJournalsRequest(journals = apiJournals, raw_days = rawDays, user_id = repo.userId)
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
                        "Cannot reach backend server.\n---\n" +
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
        repo.setError(null)
    }
}

private enum class ExpandedTool { AUTOLIFE, WELLBEING, VECTORDB, CALENDAR, LAST_RESULT }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentScreen(
    onOpenHealth: () -> Unit = {},
    viewModel: AgentViewModel = viewModel { AgentViewModel() },
) {
    val result by AnalysisRepository.result.collectAsState()
    val isLoading by AnalysisRepository.loading.collectAsState()
    val error by AnalysisRepository.error.collectAsState()
    val lastRunMs by AnalysisRepository.lastRunMs.collectAsState()
    val serviceState by PlatformStateProvider.serviceState.collectAsState()

    var expandedTool by remember { mutableStateOf<ExpandedTool?>(null) }
    val health = result?.health
    val recommendation = result?.recommendations?.firstOrNull()
    val sourceCounts = sourceCounts(
        result = result,
        lastJournalCount = viewModel.lastJournalCount,
        sensorsLive = serviceState.isRunning,
    )

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            SurfaceCard {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Top,
                ) {
                    Text(
                        text = "Current wellbeing",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    StatusPill(
                        text = when {
                            isLoading -> "Analyzing"
                            error != null -> "Needs attention"
                            result != null -> "Analysis ready"
                            else -> "Awaiting analysis"
                        },
                        color = when {
                            isLoading -> MaterialTheme.colorScheme.tertiary
                            error != null -> MaterialTheme.colorScheme.error
                            result != null -> AutoLifeSemantic.riskColor(health?.risk_level)
                            else -> MaterialTheme.colorScheme.primary
                        },
                        showDot = true,
                    )
                }
                Spacer(Modifier.height(10.dp))
                SerifHeadline(
                    text = riskHeadline(health?.risk_level ?: ""),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(16.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    ReadinessChip(
                        icon = Icons.AutoMirrored.Filled.Article,
                        label = sourceCounts.dataWindow,
                        modifier = Modifier.weight(1f),
                    )
                    ReadinessChip(
                        icon = Icons.Default.CalendarMonth,
                        label = "Last ${lastRunMs?.let { DateFormat.time(it) } ?: "--"}",
                        modifier = Modifier.weight(1f),
                    )
                }
                Spacer(Modifier.height(16.dp))
                Text(
                    text = result?.ui_summary?.summary?.takeIf { it.isNotBlank() }
                        ?: health?.behavioral_context?.takeIf { it.isNotBlank() }
                        ?: "Run analysis when you want AutoLife to combine journals, sensor markers, research, and calendar context into one focused plan.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (error != null) {
                    Spacer(Modifier.height(12.dp))
                    val parts = error!!.split("\n---\n", limit = 2)
                    ErrorCard(
                        title = "Analysis didn't run",
                        message = parts[0],
                        details = parts.getOrNull(1),
                        onRetry = if (!isLoading) { { viewModel.runAnalysis() } } else null,
                    )
                }
                Spacer(Modifier.height(18.dp))
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
            }
        }

        item {
            SectionHeader(title = "Recommended next step")
            PracticeRow(
                icon = iconForRecommendation(recommendation?.category),
                title = recommendationTitle(recommendation),
                subtitle = recommendation?.action
                    ?: "Refresh analysis to get the next best practice from your current context.",
                tags = recommendationTags(recommendation),
                accent = colorForCategory(recommendation?.category),
                onClick = onOpenHealth,
            )
        }

        if (!result?.proposed_changes.isNullOrEmpty()) {
            item {
                SectionHeader(title = "Schedule proposals")
                SurfaceCard {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        result!!.proposed_changes.take(3).forEach { change ->
                            ProposalPreviewRow(change)
                        }
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

private data class AgentSourceCounts(
    val sensorsLive: Boolean,
    val journals: String,
    val research: String,
    val calendar: String,
    val dataWindow: String,
)

private fun sourceCounts(
    result: ProcessJournalsResponse?,
    lastJournalCount: Int,
    sensorsLive: Boolean,
): AgentSourceCounts {
    val journalCount = result?.analysis_details?.journal_count?.takeIf { it > 0 } ?: lastJournalCount
    val researchCount = result?.analysis_details?.research_sources?.size ?: 0
    val eventCount = result?.calendar_summary?.event_count ?: 0
    return AgentSourceCounts(
        sensorsLive = sensorsLive,
        journals = if (journalCount > 0) "$journalCount entries" else "--",
        research = if (researchCount > 0) "$researchCount papers" else "--",
        calendar = if (eventCount > 0) "$eventCount events" else "--",
        dataWindow = if (journalCount > 0) "Based on $journalCount journals" else "No recent data",
    )
}

private fun riskHeadline(riskLevel: String): String = when (riskLevel.lowercase()) {
    "minimal", "low" -> "Stable wellbeing"
    "mild" -> "Mild stress"
    "moderate" -> "Moderate stress"
    "severe", "high" -> "High stress"
    else -> "Ready to analyze"
}

@Composable
private fun ReadinessChip(
    icon: ImageVector,
    label: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.45f)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
            Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
        }
    }
}

private fun iconForRecommendation(category: String?): ImageVector = when (category?.lowercase()) {
    "sleep" -> Icons.Default.FavoriteBorder
    "physical", "movement" -> Icons.Default.Home
    "mindfulness", "stress" -> Icons.Default.FavoriteBorder
    else -> Icons.Default.FavoriteBorder
}

@Composable
private fun colorForCategory(category: String?): Color = when (category?.lowercase()) {
    "sleep" -> AutoLifeSemantic.categoryWork
    "physical", "movement" -> AutoLifeSemantic.categoryHealth
    "mindfulness", "stress" -> AutoLifeSemantic.toolVectorDB
    "social" -> AutoLifeSemantic.categoryLeisure
    else -> MaterialTheme.colorScheme.primary
}

private fun recommendationTitle(rec: Recommendation?): String {
    if (rec == null) return "Collect a fresh read"
    return rec.category.ifBlank { "Wellbeing" }.replaceFirstChar { it.uppercase() }
}

@Composable
private fun recommendationTags(rec: Recommendation?): List<Pair<String, Color>> {
    if (rec == null) return listOf("Analysis" to MaterialTheme.colorScheme.primary)
    return listOfNotNull(
        rec.category.takeIf { it.isNotBlank() }?.replaceFirstChar { it.uppercase() }?.let {
            it to colorForCategory(rec.category)
        },
        rec.source?.takeIf { it.isNotBlank() }?.let { "Research-backed" to AutoLifeSemantic.toolVectorDB },
    )
}

@Composable
private fun ProposalPreviewRow(change: ProposedChange) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SoftIconCircle(
            icon = iconForRecommendation(change.category),
            tint = colorForCategory(change.category),
            size = 44.dp,
            iconSize = 24.dp,
        )
        Column(Modifier.weight(1f)) {
            Text(change.title ?: "Untitled proposal", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
            Text(
                text = proposalTimeLabel(change),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        CategoryBadge(
            text = change.category ?: "Health",
            color = colorForCategory(change.category),
        )
        Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private fun proposalTimeLabel(change: ProposedChange): String {
    val start = change.start_time?.replace("T", " ")?.take(16) ?: "Time pending"
    // Use positional slice so timezone offsets (e.g. +05:30) don't corrupt the result.
    val end = change.end_time?.let { t ->
        val tIdx = t.indexOf('T')
        if (tIdx >= 0 && t.length >= tIdx + 6) t.substring(tIdx + 1, tIdx + 6) else null
    }
    return if (end.isNullOrBlank()) start else "$start - $end"
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
            val kind = when (status) {
                "Ready"  -> StatusKind.Ready
                "Active" -> StatusKind.Active
                "Error"  -> StatusKind.Error
                else     -> StatusKind.Idle
            }
            StatusPill(kind = kind)
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
            ExpandedTool.WELLBEING -> "Wellbeing — Behavioral State" to AutoLifeSemantic.toolKEmo
            ExpandedTool.VECTORDB -> "VectorDB — Wellness Research" to AutoLifeSemantic.toolVectorDB
            ExpandedTool.CALENDAR -> "Calendar — Events & Tasks" to AutoLifeSemantic.toolCalendar
            ExpandedTool.LAST_RESULT -> "Full Analysis Result" to AutoLifeSemantic.riskColor(result?.health?.risk_level)
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
                ExpandedTool.WELLBEING -> WellbeingDetail(result)
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
    val locationState by PlatformStateProvider.locationState.collectAsState()
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
    SurfaceCard {
        SectionHeader(title = "Location Context")
        DataRow("Latitude", DateFormat.fmtFloat3(locationState.latitude))
        DataRow("Longitude", DateFormat.fmtFloat3(locationState.longitude))
        DataRow("WiFi networks", "${locationState.ssids.size}")
        Spacer(Modifier.height(6.dp))
        DataTextBlock("Inference source", locationState.inferenceSource)
        locationState.geocoderContext?.takeIf { it.isNotBlank() }?.let {
            DataTextBlock("Reverse geocoder address", it)
        }
        locationState.osmContext?.takeIf { it.isNotBlank() }?.let {
            DataTextBlock("OpenStreetMap nearby features", it)
        }
        locationState.wifiContext?.takeIf { it.isNotBlank() }?.let {
            DataTextBlock("Wi-Fi inferred environment", it)
        }
        if (locationState.lastInference.isNotBlank()) {
            DataTextBlock(
                label = "Gemini fused context",
                value = locationState.lastInference,
                valueColor = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun WellbeingDetail(result: ProcessJournalsResponse?) {
    val mh = result?.health
    SurfaceCard {
        SectionHeader(title = "Wellbeing Assessment")
        DataRow("State", mh?.risk_level?.replaceFirstChar { it.uppercase() } ?: "— (run analysis first)")
        DataRow("Signals", mh?.let { "${it.key_concerns.size + it.positive_indicators.size}" } ?: "—")
        if (!mh?.behavioral_context.isNullOrBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(
                text = mh!!.behavioral_context,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
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
        SectionHeader(title = "How It Works")
        Text(
            text = "The wellbeing pipeline combines journal language with behavioral signals and asks the model to form a qualitative state understanding, not a questionnaire score.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
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
            "It retrieves the top-k most relevant interventions based on your wellbeing state and journal summary, " +
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
    val mh = result.health
    SurfaceCard {
        SectionHeader(title = "Wellbeing")
        DataRow("State", mh?.risk_level?.replaceFirstChar { it.uppercase() } ?: "—")
        if (!mh?.behavioral_context.isNullOrBlank()) {
            DataRow("Context", mh!!.behavioral_context)
        }
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
        val scope = rememberCoroutineScope()
        val isApplying by ProposalApplier.isApplying.collectAsState()
        SurfaceCard {
            SectionHeader(title = "Proposed Changes (${result.proposed_changes.size})")
            result.proposed_changes.forEach { change ->
                DataRow(
                    label = change.title ?: "Untitled",
                    value = change.start_time?.replace("T", " ")?.take(16) ?: "",
                )
            }
            Spacer(Modifier.height(10.dp))
            val changes = result.proposed_changes
            Button(
                onClick = { scope.launch { ProposalApplier.apply(changes) } },
                enabled = !isApplying,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    if (isApplying) "Applying…"
                    else "Apply ${changes.size} change${if (changes.size == 1) "" else "s"} to Calendar",
                )
            }
            Text(
                text = "Review individually in the Schedule tab to apply selectively.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
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
