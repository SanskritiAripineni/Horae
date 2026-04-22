package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.*
import com.autolife.shared.repository.AnalysisRepository

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthScreen() {
    val result by AnalysisRepository.result.collectAsState()
    val isLoading by AnalysisRepository.loading.collectAsState()
    var showSources by remember { mutableStateOf(false) }

    if (result == null && isLoading) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SkeletonCard(height = 180)
            SkeletonCard(height = 120)
            SkeletonCard(height = 220)
        }
        return
    }

    if (result == null) {
        EmptyState(
            icon = Icons.Default.FavoriteBorder,
            title = "No Health Data",
            description = "Run analysis from the Agent tab to see your wellbeing assessment.",
        )
        return
    }

    val mh = result!!.health
    val ui = result!!.ui_summary
    val riskLevel = mh?.risk_level ?: "unknown"
    val riskColor = AutoLifeSemantic.riskColor(riskLevel)
    val concerns = ui?.concerns?.takeIf { it.isNotEmpty() }
        ?: mh?.key_concerns?.map { SignalItem(label = it, severity = "medium") }
        ?: emptyList()
    val protective = ui?.protective_signals?.takeIf { it.isNotEmpty() }
        ?: mh?.positive_indicators?.map { SignalItem(label = it, severity = "positive") }
        ?: emptyList()
    val evidence = ui?.evidence_chips?.takeIf { it.isNotEmpty() } ?: buildHealthEvidence(mh)

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            SurfaceCard {
                Text("Wellbeing assessment", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(6.dp))
                SerifHeadline(
                    text = ui?.headline?.takeIf { it.isNotBlank() } ?: healthHeadline(riskLevel),
                    color = riskColor,
                )
                Spacer(Modifier.height(10.dp))
                StatusPill(
                    text = ui?.confidence_label?.takeIf { it.isNotBlank() } ?: "Assessment confidence",
                    color = AutoLifeSemantic.riskMild,
                )
                Spacer(Modifier.height(14.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.CalendarMonth, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Based on ${result!!.analysis_details?.journal_count?.takeIf { it > 0 } ?: result!!.proposed_changes.size} recent inputs",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(12.dp))
                Text(
                    text = ui?.summary?.takeIf { it.isNotBlank() }
                        ?: result!!.journal_summary
                        ?: mh?.behavioral_context
                        ?: "Assessment is ready, but no summary was returned.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (evidence.isNotEmpty()) {
            item {
                SectionHeader(title = "Why this assessment")
                HealthEvidenceGrid(evidence)
            }
        }

        item {
            BoxWithConstraints {
                if (maxWidth > 520.dp) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                        SignalPanel("Concerns", concerns, "concern", Icons.Default.Warning, Modifier.weight(1f))
                        SignalPanel("Protective signals", protective, "protective", Icons.Default.CheckCircle, Modifier.weight(1f))
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SignalPanel("Concerns", concerns, "concern", Icons.Default.Warning)
                        SignalPanel("Protective signals", protective, "protective", Icons.Default.CheckCircle)
                    }
                }
            }
        }

        if (result!!.recommendations.isNotEmpty()) {
            item { SectionHeader(title = "Recommended practices") }
            items(result!!.recommendations) { rec ->
                PracticeRow(
                    icon = healthPracticeIcon(rec.category),
                    title = rec.category.ifBlank { "Wellbeing" }.replaceFirstChar { it.uppercase() },
                    subtitle = rec.action,
                    tags = listOfNotNull(
                        rec.category.takeIf { it.isNotBlank() }?.replaceFirstChar { it.uppercase() }?.let {
                            it to healthCategoryColor(rec.category)
                        },
                        rec.source?.takeIf { it.isNotBlank() }?.let { "Research-backed" to AutoLifeSemantic.toolVectorDB },
                    ),
                    accent = healthCategoryColor(rec.category),
                )
            }
        }

        item {
            SurfaceCard(modifier = Modifier.clickable { showSources = true }) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Icon(Icons.Default.Storage, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
                    Text("View evidence & sources", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                    Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        if (result!!.errors.isNotEmpty()) {
            item { SectionHeader(title = "Errors") }
            items(result!!.errors) { err ->
                ErrorCard(title = "Pipeline note", message = err)
            }
        }
    }

    if (showSources) {
        ModalBottomSheet(onDismissRequest = { showSources = false }) {
            Column(
                modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp).padding(bottom = 32.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Evidence & sources", style = MaterialTheme.typography.titleLarge)
                    IconButton(onClick = { showSources = false }) {
                        Icon(Icons.Default.Close, contentDescription = "Close")
                    }
                }
                SurfaceCard {
                    DataRow("Journals", "${result!!.analysis_details?.journal_count ?: 0}")
                    DataRow("Research sources", "${result!!.analysis_details?.research_sources?.size ?: 0}")
                    DataRow("Calendar events", "${result!!.calendar_summary?.event_count ?: 0}")
                    DataRow("Duration", "${result!!.analysis_details?.duration_seconds ?: 0.0}s")
                }
                val sensing = result!!.analysis_details?.behavioral_sensing?.toString()
                if (!sensing.isNullOrBlank() && sensing != "null") {
                    SurfaceCard {
                        SectionHeader(title = "Behavioral sensing")
                        Text(sensing, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                result!!.analysis_details?.research_sources?.take(5)?.forEach { source ->
                    SurfaceCard {
                        CategoryBadge(source.category.ifBlank { "Research" }, AutoLifeSemantic.toolVectorDB)
                        Spacer(Modifier.height(8.dp))
                        Text(source.source.ifBlank { "Unknown source" }, style = MaterialTheme.typography.titleMedium)
                        if (source.content.isNotBlank()) {
                            Spacer(Modifier.height(4.dp))
                            Text(source.content, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

private fun buildHealthEvidence(mh: MentalHealthAssessment?): List<SignalChip> {
    val chips = mutableListOf<SignalChip>()
    mh?.key_concerns?.take(3)?.forEach { chips.add(SignalChip(it, "concern", "warning")) }
    mh?.positive_indicators?.take(2)?.forEach { chips.add(SignalChip(it, "protective", "check")) }
    return chips
}

@Composable
private fun HealthEvidenceGrid(chips: List<SignalChip>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        chips.chunked(3).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                row.forEach { chip ->
                    EvidenceChip(chip.label, chip.kind, healthChipIcon(chip), Modifier.weight(1f))
                }
                repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

private fun healthChipIcon(chip: SignalChip): ImageVector = when (chip.kind.lowercase()) {
    "concern", "warning" -> Icons.Default.Warning
    "protective", "productive", "positive" -> Icons.Default.CheckCircle
    else -> Icons.Default.FavoriteBorder
}

private fun healthHeadline(riskLevel: String): String = when (riskLevel.lowercase()) {
    "minimal", "low" -> "Stable wellbeing"
    "mild" -> "Mild stress"
    "moderate" -> "Moderate stress"
    "severe", "high" -> "High stress"
    else -> "Wellbeing"
}

private fun healthPracticeIcon(category: String?): ImageVector = when (category?.lowercase()) {
    "sleep" -> Icons.Default.FavoriteBorder
    "physical", "movement" -> Icons.Default.CalendarMonth
    "mindfulness", "stress" -> Icons.Default.FavoriteBorder
    else -> Icons.Default.FavoriteBorder
}

@Composable
private fun healthCategoryColor(category: String?): Color = when (category?.lowercase()) {
    "sleep" -> AutoLifeSemantic.categoryWork
    "physical", "movement" -> AutoLifeSemantic.categoryHealth
    "mindfulness", "stress" -> AutoLifeSemantic.toolVectorDB
    "social" -> AutoLifeSemantic.categoryLeisure
    else -> MaterialTheme.colorScheme.primary
}
