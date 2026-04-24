package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.autolife.composeapp.ui.DateFormat
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.*
import com.autolife.shared.repository.AnalysisRepository

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthScreen(
    onOpenAgent: () -> Unit = {},
    onOpenSchedule: () -> Unit = {},
) {
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
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                SurfaceCard {
                    ActionableEmptyState(
                        icon = Icons.Default.FavoriteBorder,
                        title = "No health assessment yet",
                        description = "Run an analysis to turn journals, sensor markers, and schedule context into a participant-friendly wellbeing read.",
                        action = {
                            Button(onClick = onOpenAgent) {
                                Text("Go to Agent")
                            }
                        },
                    )
                }
            }
        }
        return
    }

    val mh = result!!.health
    val ui = result!!.ui_summary
    val concerns = ui?.concerns?.takeIf { it.isNotEmpty() }
        ?: mh?.key_concerns?.map { SignalItem(label = it, severity = "medium") }
        ?: emptyList()
    val positiveSignals = ui?.protective_signals?.takeIf { it.isNotEmpty() }
        ?: ui?.productive_signals?.takeIf { it.isNotEmpty() }
        ?: mh?.positive_indicators?.map { SignalItem(label = it, severity = "positive") }
        ?: emptyList()
    val sourceTitles = result!!.analysis_details?.research_sources
        .orEmpty()
        .mapNotNull { it.source.takeIf(String::isNotBlank) }
        .distinct()
    val wellbeingNarrative = wellbeingNarrative(
        uiSummary = ui?.summary,
        behavioralContext = mh?.behavioral_context,
        journalSummary = result!!.journal_summary,
    )

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
                    text = ui?.headline?.takeIf { it.isNotBlank() } ?: healthHeadline(mh?.risk_level ?: "unknown"),
                    color = AutoLifeSemantic.riskColor(mh?.risk_level ?: "unknown"),
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
                    text = wellbeingNarrative,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        item {
            BoxWithConstraints {
                if (maxWidth > 520.dp) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                        SignalPanel("Concerns", concerns, "concern", Icons.Default.Warning, Modifier.weight(1f))
                        SignalPanel("Positive signals", positiveSignals, "positive", Icons.Default.CheckCircle, Modifier.weight(1f))
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SignalPanel("Concerns", concerns, "concern", Icons.Default.Warning)
                        SignalPanel("Positive signals", positiveSignals, "positive", Icons.Default.CheckCircle)
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
                    showChevron = false,
                )
            }
            item {
                Button(
                    onClick = onOpenSchedule,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Implement these practices")
                }
            }
        }

        item {
            SurfaceCard(modifier = Modifier.clickable { showSources = true }) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Icon(Icons.Default.Storage, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
                    Text("View sources", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
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
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp)
                    .padding(bottom = 32.dp),
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
                    SectionHeader(title = "Sources")
                    if (sourceTitles.isEmpty()) {
                        Text(
                            "No source titles were returned for this run.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        sourceTitles.forEachIndexed { index, title ->
                            if (index > 0) {
                                Spacer(Modifier.height(10.dp))
                            }
                            Text(
                                title,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun healthHeadline(riskLevel: String): String = when (riskLevel.lowercase()) {
    "minimal", "low" -> "Stable wellbeing"
    "mild" -> "Mild stress"
    "moderate" -> "Moderate stress"
    "severe", "high" -> "High stress"
    else -> "Wellbeing"
}

private fun wellbeingNarrative(
    uiSummary: String?,
    behavioralContext: String?,
    journalSummary: String?,
): String {
    val parts = listOf(uiSummary, behavioralContext, journalSummary)
        .map { it.orEmpty().trim() }
        .filter { it.isNotBlank() }
        .distinct()
    return parts.take(2).joinToString("\n\n").ifBlank {
        "Assessment is ready, but no summary was returned."
    }
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
