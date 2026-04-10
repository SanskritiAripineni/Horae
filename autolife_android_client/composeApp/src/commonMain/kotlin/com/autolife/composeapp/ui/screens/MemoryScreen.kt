package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.HealthHistoryEntry
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.repository.AnalysisRepository
import kotlinx.coroutines.launch

class MemoryViewModel : ViewModel() {
    var isLoading by mutableStateOf(false)
        private set
    var fetchError by mutableStateOf<String?>(null)
        private set

    init { fetch() }

    fun fetch() {
        viewModelScope.launch {
            isLoading = true
            fetchError = null
            try {
                val data = AutoLifeApi.getMemory()
                AnalysisRepository.setMemory(data)
            } catch (e: Exception) {
                fetchError = e.message
            } finally {
                isLoading = false
            }
        }
    }
}

@Composable
fun MemoryScreen(viewModel: MemoryViewModel = viewModel { MemoryViewModel() }) {
    val memory by AnalysisRepository.memory.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Header with loading/error state
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Memory",
                    style = MaterialTheme.typography.headlineMedium,
                )
                if (viewModel.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    FilledTonalButton(onClick = { viewModel.fetch() }) {
                        Text("Refresh")
                    }
                }
            }
            if (viewModel.fetchError != null) {
                Spacer(Modifier.height(4.dp))
                Text(
                    text = viewModel.fetchError!!,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }

        if (memory != null) {
            val prefs = memory!!.preferences
            val mh = memory!!.mental_health

            // User preferences
            item {
                SectionHeader(title = "Preferences")
                SurfaceCard {
                    DataRow(
                        label = "Work Hours",
                        value = "${prefs.work_hours.getOrElse(0) { 9 }}:00 – ${prefs.work_hours.getOrElse(1) { 17 }}:00",
                    )
                    DataRow(
                        label = "Max Daily Hours",
                        value = "${prefs.max_daily_hours}h",
                    )
                    if (prefs.goals.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = "Goals",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Spacer(Modifier.height(4.dp))
                        prefs.goals.forEach { goal ->
                            Text(
                                text = "  •  $goal",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurface,
                                modifier = Modifier.padding(vertical = 2.dp),
                            )
                        }
                    }
                    if (prefs.preferred_interventions.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            text = "Interventions",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = prefs.preferred_interventions.joinToString(", "),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            // Mental health tracking
            item {
                SectionHeader(title = "Mental Health")
                SurfaceCard {
                    DataRow(
                        label = "Latest PHQ-4",
                        value = "${mh.latest_phq4 ?: "—"} / 12",
                        valueColor = AutoLifeSemantic.riskColor(mh.risk_level),
                    )
                    DataRow(
                        label = "Risk Level",
                        value = mh.risk_level.replaceFirstChar { it.uppercase() },
                        valueColor = AutoLifeSemantic.riskColor(mh.risk_level),
                    )
                    DataRow(
                        label = "Trend",
                        value = mh.trend.replaceFirstChar { it.uppercase() },
                    )
                    DataRow(
                        label = "History",
                        value = "${mh.history.size} entries",
                    )

                    // Sparkline
                    if (mh.history.size >= 2) {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            text = "PHQ-4 Over Time",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(6.dp))
                        Sparkline(history = mh.history)
                        Spacer(Modifier.height(4.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                text = mh.history.first().timestamp.take(10),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                text = mh.history.last().timestamp.take(10),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            // History list
            if (mh.history.isNotEmpty()) {
                item { SectionHeader(title = "History") }
                items(mh.history.reversed()) { entry ->
                    HistoryRow(entry)
                }
            }
        } else if (!viewModel.isLoading) {
            item {
                EmptyState(
                    icon = Icons.Default.Storage,
                    title = "No Memory Data",
                    description = "Run analysis or ensure the backend is reachable.",
                    action = {
                        Button(onClick = { viewModel.fetch() }) {
                            Text("Refresh")
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun Sparkline(history: List<HealthHistoryEntry>) {
    val lineColor = AutoLifeSemantic.riskColor(history.last().risk_level)
    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(72.dp)
    ) {
        if (history.size < 2) return@Canvas

        val maxScore = 12f
        val path = Path()

        history.forEachIndexed { i, entry ->
            val x = i.toFloat() / (history.size - 1) * size.width
            val y = size.height - (entry.total.coerceIn(0, 12) / maxScore) * size.height
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }

        // Grid lines at 0, 4, 8, 12
        listOf(0f, 4f, 8f, 12f).forEach { score ->
            val y = size.height - (score / maxScore) * size.height
            drawLine(
                color = gridColor,
                start = Offset(0f, y),
                end = Offset(size.width, y),
                strokeWidth = 1f,
            )
        }

        drawPath(path = path, color = lineColor, style = Stroke(width = 2.dp.toPx()))

        // Data point dots
        history.forEachIndexed { i, entry ->
            val x = i.toFloat() / (history.size - 1) * size.width
            val y = size.height - (entry.total.coerceIn(0, 12) / maxScore) * size.height
            drawCircle(color = lineColor, radius = 3.dp.toPx(), center = Offset(x, y))
        }
    }
}

@Composable
private fun HistoryRow(entry: HealthHistoryEntry) {
    val rc = AutoLifeSemantic.riskColor(entry.risk_level)

    SurfaceCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = entry.timestamp.take(10),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "PHQ-4: ${entry.total}",
                style = MaterialTheme.typography.bodyMedium,
                color = rc,
            )
            StatusPill(
                text = entry.risk_level.replaceFirstChar { it.uppercase() },
                color = rc,
            )
        }
    }
}
