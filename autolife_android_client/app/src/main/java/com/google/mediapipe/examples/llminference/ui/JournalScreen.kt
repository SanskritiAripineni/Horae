package com.google.mediapipe.examples.llminference.ui

import android.app.Application
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.launch
import com.google.mediapipe.examples.llminference.AutoLifeApp
import com.google.mediapipe.examples.llminference.data.DebugRepository
import com.google.mediapipe.examples.llminference.data.JournalEntry
import com.google.mediapipe.examples.llminference.data.SensorLog
import com.google.mediapipe.examples.llminference.ui.theme.*
import java.text.SimpleDateFormat
import java.util.*

// ── ViewModel ─────────────────────────────────────────────────

class JournalViewModel(application: Application) : AndroidViewModel(application) {
    private val dao = (application as AutoLifeApp).database.logDao()
    val journals   = dao.observeJournals()
    val recentLogs = dao.observeRecentLogs()

    fun clearJournals() = viewModelScope.launch { dao.deleteAllJournals() }
    fun clearLogs()     = viewModelScope.launch { dao.deleteAllLogs() }
}

// ── Screen ────────────────────────────────────────────────────

@Composable
fun JournalScreen(viewModel: JournalViewModel = viewModel()) {
    val journals   by viewModel.journals.collectAsStateWithLifecycle(initialValue = emptyList())
    val logs       by viewModel.recentLogs.collectAsStateWithLifecycle(initialValue = emptyList())
    val isRunning  by DebugRepository.isServiceRunning.collectAsStateWithLifecycle()
    val motionStats by DebugRepository.motionStats.collectAsStateWithLifecycle()

    var selectedTab by rememberSaveable { mutableStateOf(0) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
    ) {
        // ── Status header ────────────────────────────────────
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            shape = RoundedCornerShape(2.dp),
            colors = CardDefaults.cardColors(containerColor = DarkSurface),
            border = BorderStroke(1.dp, DarkBorder)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(10.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(7.dp)
                                .background(
                                    if (isRunning) TerminalGreen else DarkOnSurfaceDim,
                                    RoundedCornerShape(50)
                                )
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "AUTOLIFE JOURNAL",
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                    Text(
                        "service: ${if (isRunning) "[RUNNING]" else "[STOPPED]"}",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isRunning) TerminalGreen else DarkOnSurfaceDim
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        "motion: ${motionStats.detectedClass}",
                        style = MaterialTheme.typography.labelSmall,
                        color = ToolAutoLife
                    )
                    Text(
                        "logs: ${logs.size}  journals: ${journals.size}",
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                }
            }
        }

        // ── Clear buttons ────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick  = { viewModel.clearJournals() },
                modifier = Modifier.weight(1f),
                shape    = RoundedCornerShape(2.dp),
                colors   = ButtonDefaults.outlinedButtonColors(contentColor = TerminalRed),
                border   = BorderStroke(1.dp, TerminalRed)
            ) {
                Text("CLR JOURNALS", style = MaterialTheme.typography.labelLarge)
            }
            OutlinedButton(
                onClick  = { viewModel.clearLogs() },
                modifier = Modifier.weight(1f),
                shape    = RoundedCornerShape(2.dp),
                colors   = ButtonDefaults.outlinedButtonColors(contentColor = TerminalRed),
                border   = BorderStroke(1.dp, TerminalRed)
            ) {
                Text("CLR LOGS", style = MaterialTheme.typography.labelLarge)
            }
        }

        // ── Tabs ─────────────────────────────────────────────
        TabRow(
            selectedTabIndex = selectedTab,
            containerColor = DarkSurface,
            contentColor = TerminalGreen
        ) {
            Tab(
                selected = selectedTab == 0,
                onClick = { selectedTab = 0 },
                text = {
                    Text(
                        "JOURNALS",
                        style = MaterialTheme.typography.labelLarge,
                        color = if (selectedTab == 0) TerminalGreen else DarkOnSurfaceDim
                    )
                }
            )
            Tab(
                selected = selectedTab == 1,
                onClick = { selectedTab = 1 },
                text = {
                    Text(
                        "LIVE LOGS",
                        style = MaterialTheme.typography.labelLarge,
                        color = if (selectedTab == 1) TerminalGreen else DarkOnSurfaceDim
                    )
                }
            )
        }

        when (selectedTab) {
            0 -> JournalsList(journals)
            1 -> LogsList(logs)
        }
    }
}

// ── Journal entries list ──────────────────────────────────────

@Composable
private fun JournalsList(journals: List<JournalEntry>) {
    if (journals.isEmpty()) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(DarkBackground),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("NO JOURNALS", style = MaterialTheme.typography.titleLarge, color = DarkOnSurfaceDim)
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Start the AutoLife service to begin collecting data.",
                    style = MaterialTheme.typography.labelMedium,
                    color = DarkOnSurfaceDim
                )
            }
        }
        return
    }

    val sdfDate = SimpleDateFormat("MMM d  HH:mm", Locale.getDefault())
    val sdfTime = SimpleDateFormat("HH:mm", Locale.getDefault())

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(horizontal = 12.dp),
        contentPadding = PaddingValues(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        items(journals.reversed(), key = { it.id }) { entry ->
            JournalEntryCard(
                entry   = entry,
                sdfDate = sdfDate,
                sdfTime = sdfTime
            )
        }
    }
}

@Composable
private fun JournalEntryCard(
    entry: JournalEntry,
    sdfDate: SimpleDateFormat,
    sdfTime: SimpleDateFormat
) {
    var expanded by rememberSaveable(entry.id) { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded },
        shape = RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, DarkBorder)
    ) {
        Row(modifier = Modifier.height(IntrinsicSize.Min)) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .fillMaxHeight()
                    .background(ToolAutoLife)
            )
            Column(modifier = Modifier.padding(10.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        "── ${sdfDate.format(Date(entry.createdTimestamp))}",
                        style = MaterialTheme.typography.labelLarge,
                        color = ToolAutoLife
                    )
                    Text(
                        if (expanded) "▲" else "▼",
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                }
                Text(
                    "period: ${sdfTime.format(Date(entry.periodStart))} – ${sdfTime.format(Date(entry.periodEnd))}",
                    style = MaterialTheme.typography.labelSmall,
                    color = DarkOnSurfaceDim
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    entry.content,
                    style = MaterialTheme.typography.bodyMedium,
                    color = DarkOnSurface,
                    maxLines = if (expanded) Int.MAX_VALUE else 4
                )
                if (!expanded && entry.content.length > 200) {
                    Text(
                        "tap to expand",
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim,
                        fontStyle = FontStyle.Italic
                    )
                }
            }
        }
    }
}
