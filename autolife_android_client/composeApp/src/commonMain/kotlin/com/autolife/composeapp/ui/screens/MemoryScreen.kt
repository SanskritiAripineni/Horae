package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
                Spacer(Modifier.height(8.dp))
                ErrorCard(
                    title = "Couldn't load memory",
                    message = "We couldn't reach the backend. Tap retry or check your connection.",
                    details = viewModel.fetchError,
                    onRetry = { viewModel.fetch() },
                )
            }
        }

        if (memory == null && viewModel.isLoading) {
            item { SkeletonCard(height = 80) }
            item { SkeletonCard(height = 220) }
        }

        if (memory != null) {
            val prefs = memory!!.preferences
            val mh = memory!!.health

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

            // Wellbeing tracking
            item {
                SectionHeader(title = "Wellbeing")
                SurfaceCard {
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
                text = entry.risk_level.replaceFirstChar { it.uppercase() },
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
