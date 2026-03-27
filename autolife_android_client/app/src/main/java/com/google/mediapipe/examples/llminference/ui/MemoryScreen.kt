package com.google.mediapipe.examples.llminference.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mediapipe.examples.llminference.data.AnalysisRepository
import com.google.mediapipe.examples.llminference.network.BackendApiClient
import com.google.mediapipe.examples.llminference.network.HealthHistoryEntry
import com.google.mediapipe.examples.llminference.ui.theme.*
import kotlinx.coroutines.launch

// ── ViewModel ─────────────────────────────────────────────────

class MemoryViewModel : ViewModel() {
    var isLoading  by mutableStateOf(false)
    var fetchError by mutableStateOf<String?>(null)

    init { fetch() }

    fun fetch() {
        viewModelScope.launch {
            isLoading = true
            fetchError = null
            try {
                val data = BackendApiClient.apiService.getMemory()
                AnalysisRepository.setMemory(data)
            } catch (e: Exception) {
                fetchError = "err: ${e.message}"
            } finally {
                isLoading = false
            }
        }
    }
}

// ── Screen ────────────────────────────────────────────────────

@Composable
fun MemoryScreen(viewModel: MemoryViewModel = viewModel()) {
    val memory by AnalysisRepository.memory.collectAsStateWithLifecycle()

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(horizontal = 12.dp),
        contentPadding = PaddingValues(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // ── Module header ────────────────────────────────────
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(2.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF0A1F0A)),
                border = BorderStroke(1.dp, TerminalGreen)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            "MEMORY MODULE",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = TerminalGreen
                        )
                        Text(
                            "User Prefs  ·  Mental Health Tracking",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim
                        )
                    }
                    if (viewModel.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = TerminalGreen,
                            strokeWidth = 2.dp
                        )
                    } else {
                        StatusBadge(
                            if (memory != null) "LOADED" else "NO DATA",
                            color = if (memory != null) TerminalGreen else DarkOnSurfaceDim
                        )
                    }
                }
            }
            if (viewModel.fetchError != null) {
                Text(
                    viewModel.fetchError!!,
                    style = MaterialTheme.typography.labelMedium,
                    color = TerminalRed,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        if (memory != null) {
            val prefs = memory!!.preferences
            val mh    = memory!!.mental_health

            // ── User preferences ─────────────────────────────
            item {
                SectionHeader("USER PREFERENCES")
                TerminalCard(accentColor = TerminalGreen) {
                    MonoRow("user_id",       memory!!.user_id)
                    MonoRow("work_hours",    "${prefs.work_hours.getOrElse(0) { 9 }}:00 – ${prefs.work_hours.getOrElse(1) { 17 }}:00")
                    MonoRow("max_daily_hrs", "${prefs.max_daily_hours}h")
                    if (prefs.goals.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "goals:",
                            style = MaterialTheme.typography.labelMedium,
                            color = DarkOnSurfaceDim
                        )
                        prefs.goals.forEach { goal ->
                            Text(
                                "  • $goal",
                                style = MaterialTheme.typography.bodyMedium,
                                color = DarkOnSurface
                            )
                        }
                    }
                    if (prefs.preferred_interventions.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "interventions:",
                            style = MaterialTheme.typography.labelMedium,
                            color = DarkOnSurfaceDim
                        )
                        Text(
                            prefs.preferred_interventions.joinToString(", "),
                            style = MaterialTheme.typography.bodyMedium,
                            color = DarkOnSurface
                        )
                    }
                }
            }

            // ── Mental health tracking ────────────────────────
            item {
                SectionHeader("MENTAL HEALTH TRACKING")
                TerminalCard(accentColor = riskColor(mh.risk_level)) {
                    MonoRow("latest_phq4",  "${mh.latest_phq4 ?: "─"} / 12")
                    MonoRow("risk_level",   "[${mh.risk_level.uppercase()}]",  valueColor = riskColor(mh.risk_level))
                    MonoRow("trend",        mh.trend.uppercase())
                    MonoRow("history",      "${mh.history.size} entries")

                    // Sparkline
                    if (mh.history.size >= 2) {
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            "PHQ-4 over time",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Sparkline(history = mh.history)
                        Spacer(modifier = Modifier.height(4.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                mh.history.first().timestamp.take(10),
                                style = MaterialTheme.typography.labelSmall,
                                color = DarkOnSurfaceDim
                            )
                            Text(
                                mh.history.last().timestamp.take(10),
                                style = MaterialTheme.typography.labelSmall,
                                color = DarkOnSurfaceDim
                            )
                        }
                    }
                }
            }

            // ── History list ──────────────────────────────────
            if (mh.history.isNotEmpty()) {
                item { SectionHeader("HISTORY") }
                items(mh.history.reversed()) { entry ->
                    HistoryRow(entry)
                }
            }
        } else if (!viewModel.isLoading) {
            // Empty state
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 40.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("NO MEMORY DATA", style = MaterialTheme.typography.titleLarge, color = DarkOnSurfaceDim)
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "Run analysis or ensure the backend is reachable.",
                            style = MaterialTheme.typography.labelMedium,
                            color = DarkOnSurfaceDim
                        )
                    }
                }
            }
        }

        // ── Refresh button ───────────────────────────────────
        item {
            Spacer(modifier = Modifier.height(4.dp))
            OutlinedButton(
                onClick = { viewModel.fetch() },
                enabled = !viewModel.isLoading,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(2.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = TerminalGreen),
                border = BorderStroke(1.dp, if (!viewModel.isLoading) TerminalGreen else DarkBorder)
            ) {
                Text(
                    if (viewModel.isLoading) "█  LOADING..." else "⟳  REFRESH FROM BACKEND",
                    style = MaterialTheme.typography.labelLarge
                )
            }
        }
    }
}

// ── Sparkline ─────────────────────────────────────────────────

@Composable
private fun Sparkline(history: List<HealthHistoryEntry>) {
    val lineColor = riskColor(history.last().risk_level)
    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(72.dp)
    ) {
        if (history.size < 2) return@Canvas

        val maxScore = 12f
        val path     = Path()

        history.forEachIndexed { i, entry ->
            val x = i.toFloat() / (history.size - 1) * size.width
            val y = size.height - (entry.total.coerceIn(0, 12) / maxScore) * size.height
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }

        // Grid lines at 0, 4, 8, 12
        listOf(0f, 4f, 8f, 12f).forEach { score ->
            val y = size.height - (score / maxScore) * size.height
            drawLine(
                color       = Color(0xFF2A2A2A),
                start       = Offset(0f, y),
                end         = Offset(size.width, y),
                strokeWidth = 1f
            )
        }

        drawPath(
            path   = path,
            color  = lineColor,
            style  = Stroke(width = 2.dp.toPx())
        )

        // Data point dots
        history.forEachIndexed { i, entry ->
            val x = i.toFloat() / (history.size - 1) * size.width
            val y = size.height - (entry.total.coerceIn(0, 12) / maxScore) * size.height
            drawCircle(color = lineColor, radius = 3.dp.toPx(), center = Offset(x, y))
        }
    }
}

// ── History row ───────────────────────────────────────────────

@Composable
private fun HistoryRow(entry: HealthHistoryEntry) {
    val rc = riskColor(entry.risk_level)
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, DarkBorder)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                entry.timestamp.take(10),
                style = MaterialTheme.typography.labelLarge,
                color = DarkOnSurfaceDim
            )
            Text(
                "phq4: ${entry.total.toString().padStart(2, '0')}",
                style = MaterialTheme.typography.labelLarge,
                color = rc
            )
            Text(
                "[${entry.risk_level.uppercase()}]",
                style = MaterialTheme.typography.labelMedium,
                color = rc
            )
        }
    }
}
