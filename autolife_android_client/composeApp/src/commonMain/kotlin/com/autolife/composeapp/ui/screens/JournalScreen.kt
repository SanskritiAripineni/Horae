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
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Warning
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
import com.autolife.composeapp.ui.SnackbarBus
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
fun JournalScreen(
    onServiceToggle: (Boolean) -> Unit = {},
    viewModel: JournalViewModel = viewModel { JournalViewModel() },
) {
    val journals by viewModel.journals.collectAsState(initial = emptyList())
    val logs by viewModel.recentLogs.collectAsState(initial = emptyList())
    val serviceState by PlatformStateProvider.serviceState.collectAsState()
    val motionState by PlatformStateProvider.motionState.collectAsState()

    var selectedTab by rememberSaveable { mutableIntStateOf(0) }

    Column(modifier = Modifier.fillMaxSize()) {
        // Status bar
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            ScreenIntro(
                title = "Journal",
                subtitle = "Review generated day summaries and live collection logs.",
            )
            InfoStatusCard(
                icon = if (serviceState.isRunning) Icons.Default.CheckCircle else Icons.Default.PlayArrow,
                title = if (serviceState.isRunning) "Collection is active" else "Collection is paused",
                subtitle = "${logs.size} logs · ${journals.size} journals · ${motionState.detectedClass}",
                status = if (serviceState.isRunning) "Collecting" else "Paused",
                statusColor = if (serviceState.isRunning) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant,
                action = if (!serviceState.isRunning) {
                    {
                        TextButton(onClick = { onServiceToggle(true) }) {
                            Text("Start")
                        }
                    }
                } else {
                    null
                }
            )
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

    var showClearDialog by remember { mutableStateOf(false) }
    if (showClearDialog) {
        ConfirmClearDialog(
            title = "Clear all journals?",
            body = "This deletes ${journals.size} journal ${if (journals.size == 1) "entry" else "entries"} from the local database. This cannot be undone.",
            onConfirm = {
                val count = journals.size
                showClearDialog = false
                viewModel.clearJournals()
                SnackbarBus.tryEmit("Cleared $count journal${if (count == 1) "" else "s"}")
            },
            onDismiss = { showClearDialog = false },
        )
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
                OutlinedButton(onClick = { showClearDialog = true }) {
                    Text("Clear all")
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
        val hasError = entry.content.contains("No response", ignoreCase = true) ||
            entry.content.contains("failed", ignoreCase = true)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column {
                Text(
                    text = DateFormat.dateTime(entry.createdTimestamp),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "${DateFormat.time(entry.periodStart)} - ${DateFormat.time(entry.periodEnd)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            StatusPill(
                text = if (hasError) "Needs retry" else if (expanded) "Open" else "Generated",
                color = if (hasError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.secondary,
                showDot = true,
            )
        }
        Spacer(Modifier.height(8.dp))
        if (hasError) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(18.dp))
                Text(
                    text = "The generator did not return a summary for this window.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(8.dp))
        }
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
                color = if (hasError) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                maxLines = 3,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Tap to ${if (expanded) "hide" else "expand"}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
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

    var showClearDialog by remember { mutableStateOf(false) }
    if (showClearDialog) {
        ConfirmClearDialog(
            title = "Clear all sensor logs?",
            body = "This deletes ${logs.size} log entries from the local database. This cannot be undone.",
            onConfirm = {
                val count = logs.size
                showClearDialog = false
                viewModel.clearLogs()
                SnackbarBus.tryEmit("Cleared $count log${if (count == 1) "" else "s"}")
            },
            onDismiss = { showClearDialog = false },
        )
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
                OutlinedButton(onClick = { showClearDialog = true }) {
                    Text("Clear all")
                }
            }
        }
        items(logs, key = { it.id }) { log ->
            LogCard(log)
        }
    }
}

@Composable
private fun ConfirmClearDialog(
    title: String,
    body: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(body) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text("Clear All", color = MaterialTheme.colorScheme.error)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
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
