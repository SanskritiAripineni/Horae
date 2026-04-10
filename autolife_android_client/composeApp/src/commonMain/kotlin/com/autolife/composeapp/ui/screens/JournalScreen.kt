package com.autolife.composeapp.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.ui.DateFormat
import com.autolife.composeapp.ui.components.*
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.JournalEntry
import com.autolife.shared.model.SensorLog
import kotlinx.coroutines.launch

class JournalViewModel : ViewModel() {
    val journals = DatabaseRepository.observeJournals()
    val recentLogs = DatabaseRepository.observeRecentLogs()

    fun clearJournals() = viewModelScope.launch { DatabaseRepository.deleteAllJournals() }
    fun clearLogs() = viewModelScope.launch { DatabaseRepository.deleteAllLogs() }
}

@Composable
fun JournalScreen(viewModel: JournalViewModel = viewModel { JournalViewModel() }) {
    val journals by viewModel.journals.collectAsState(initial = emptyList())
    val logs by viewModel.recentLogs.collectAsState(initial = emptyList())
    val serviceState by PlatformStateProvider.serviceState.collectAsState()
    val motionState by PlatformStateProvider.motionState.collectAsState()

    var selectedTab by rememberSaveable { mutableIntStateOf(0) }

    Column(modifier = Modifier.fillMaxSize()) {
        // Status bar
        SurfaceCard(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        text = "Journal",
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(
                        text = if (serviceState.isRunning) "Service active" else "Service stopped",
                        style = MaterialTheme.typography.labelMedium,
                        color = if (serviceState.isRunning) MaterialTheme.colorScheme.secondary
                                else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = motionState.detectedClass,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Text(
                        text = "${logs.size} logs  ·  ${journals.size} journals",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        // Tabs
        PrimaryTabRow(
            selectedTabIndex = selectedTab,
            containerColor = MaterialTheme.colorScheme.surface,
            contentColor = MaterialTheme.colorScheme.primary,
        ) {
            Tab(
                selected = selectedTab == 0,
                onClick = { selectedTab = 0 },
                text = { Text("Journals") },
                modifier = Modifier.testTag("tab_journals"),
            )
            Tab(
                selected = selectedTab == 1,
                onClick = { selectedTab = 1 },
                text = { Text("Live Logs") },
                modifier = Modifier.testTag("tab_live_logs"),
            )
        }

        when (selectedTab) {
            0 -> JournalsList(journals, viewModel)
            1 -> LogsList(logs, viewModel)
        }
    }
}

@Composable
private fun JournalsList(journals: List<JournalEntry>, viewModel: JournalViewModel) {
    if (journals.isEmpty()) {
        EmptyState(
            icon = Icons.AutoMirrored.Filled.Article,
            title = "No Journals Yet",
            description = "Start the AutoLife service to begin collecting data and generating journals.",
        )
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(onClick = { viewModel.clearJournals() }) {
                    Text("Clear All", color = MaterialTheme.colorScheme.error)
                }
            }
        }
        items(journals.reversed(), key = { it.id }) { entry ->
            JournalEntryCard(entry)
        }
    }
}

@Composable
private fun JournalEntryCard(entry: JournalEntry) {
    var expanded by rememberSaveable(entry.id) { mutableStateOf(false) }

    SurfaceCard(
        modifier = Modifier.clickable { expanded = !expanded }
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = DateFormat.dateTime(entry.createdTimestamp),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = if (expanded) "Hide" else "Show",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
        }
        Text(
            text = "${DateFormat.time(entry.periodStart)} – ${DateFormat.time(entry.periodEnd)}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        AnimatedVisibility(
            visible = expanded,
            enter = expandVertically(),
            exit = shrinkVertically(),
        ) {
            Text(
                text = entry.content,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
        if (!expanded) {
            Text(
                text = entry.content,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 3,
            )
        }
    }
}

@Composable
private fun LogsList(logs: List<SensorLog>, viewModel: JournalViewModel) {
    if (logs.isEmpty()) {
        EmptyState(
            icon = Icons.AutoMirrored.Filled.Article,
            title = "No Logs Yet",
            description = "Sensor logs will appear here when the service is running.",
        )
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(onClick = { viewModel.clearLogs() }) {
                    Text("Clear All", color = MaterialTheme.colorScheme.error)
                }
            }
        }
        items(logs, key = { it.id }) { log ->
            LogCard(log)
        }
    }
}

@Composable
private fun LogCard(log: SensorLog) {
    val typeColor = when (log.type.lowercase()) {
        "motion"   -> MaterialTheme.colorScheme.secondary
        "location" -> MaterialTheme.colorScheme.primary
        "wifi"     -> MaterialTheme.colorScheme.tertiary
        else       -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    SurfaceCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            StatusPill(text = log.type.uppercase(), color = typeColor)
            Text(
                text = DateFormat.time(log.timestamp),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.height(6.dp))
        Text(
            text = log.content,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 4,
        )
    }
}
