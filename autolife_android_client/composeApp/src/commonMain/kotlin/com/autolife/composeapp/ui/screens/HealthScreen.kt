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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.*
import com.autolife.shared.repository.AnalysisRepository

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthScreen(
    onOpenAgent: () -> Unit = {},
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
                        description = "Run an analysis to turn your journals, sensor data, and calendar context into a personalized wellbeing read.",
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
    val researchSources = result!!.analysis_details?.research_sources
        .orEmpty()
        .filter { it.source.isNotBlank() }
        .distinctBy { it.source }
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
                        SignalPanel("Concerns", concerns, "concern", Icons.Default.Warning, Modifier.weight(1f), onClick = { showSources = true })
                        SignalPanel("Positive signals", positiveSignals, "positive", Icons.Default.CheckCircle, Modifier.weight(1f), onClick = { showSources = true })
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SignalPanel("Concerns", concerns, "concern", Icons.Default.Warning, onClick = { showSources = true })
                        SignalPanel("Positive signals", positiveSignals, "positive", Icons.Default.CheckCircle, onClick = { showSources = true })
                    }
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
                verticalArrangement = Arrangement.spacedBy(16.dp),
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

                // Sources section
                SurfaceCard {
                    SectionHeader(title = "Sources")
                    Spacer(Modifier.height(4.dp))
                    if (researchSources.isEmpty()) {
                        Text(
                            "No source titles were returned for this run.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        researchSources.forEachIndexed { index, source ->
                            if (index > 0) MutedDivider()
                            Column(
                                modifier = Modifier.padding(vertical = 10.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                if (source.category.isNotBlank()) {
                                    CategoryBadge(
                                        text = source.category,
                                        color = AutoLifeSemantic.toolVectorDB,
                                    )
                                    Spacer(Modifier.height(4.dp))
                                }
                                Text(
                                    text = source.source,
                                    style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                                if (source.content.isNotBlank()) {
                                    Text(
                                        text = source.content.take(120) + if (source.content.length > 120) "…" else "",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }
                }

                // Sensor signals section
                SectionHeader(title = "Data powering this read")
                SurfaceCard {
                    val markerDomains = listOf(
                        Triple("Sleep",    "Bedtime · Duration · Regularity",               MaterialTheme.colorScheme.tertiary),
                        Triple("Screen",   "Late-night use · Daily screen time · App focus", MaterialTheme.colorScheme.primary),
                        Triple("Movement", "Movement variety · Familiar places",             MaterialTheme.colorScheme.secondary),
                        Triple("Social",   "Daily rhythm · Communication balance",           AutoLifeSemantic.categoryLeisure),
                    )
                    markerDomains.forEachIndexed { index, (domain, markers, color) ->
                        if (index > 0) MutedDivider()
                        Column(
                            modifier = Modifier.padding(vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            CategoryBadge(text = domain, color = color)
                            Text(
                                text = markers,
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
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
