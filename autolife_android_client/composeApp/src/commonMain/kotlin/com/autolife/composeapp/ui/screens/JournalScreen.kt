package com.autolife.composeapp.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.runtime.saveable.rememberSaveable
import com.autolife.composeapp.ui.components.withSerif
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.ui.DateFormat
import com.autolife.composeapp.ui.SnackbarBus
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.JournalEntry
import com.autolife.shared.model.SensorLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.IO
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class JournalViewModel : ViewModel() {
    val journals = DatabaseRepository.observeJournals()
    val recentLogs = DatabaseRepository.observeRecentLogs()

    fun clearJournals() = viewModelScope.launch {
        withContext(Dispatchers.IO) { DatabaseRepository.deleteAllJournals() }
    }

    fun clearLogs() = viewModelScope.launch {
        withContext(Dispatchers.IO) { DatabaseRepository.deleteAllLogs() }
    }
}

@Composable
fun JournalScreen(
    onServiceToggle: (Boolean) -> Unit = {},
    viewModel: JournalViewModel = viewModel { JournalViewModel() },
) {
    val journals by viewModel.journals.collectAsState(initial = emptyList())
    val logs by viewModel.recentLogs.collectAsState(initial = emptyList())
    val serviceState by PlatformStateProvider.serviceState.collectAsState()

    var showClearDialog by remember { mutableStateOf(false) }

    if (showClearDialog) {
        ConfirmClearDialog(
            title = "Clear all journals?",
            body = "This deletes ${journals.size} ${if (journals.size == 1) "journal" else "journals"} from the local database. This cannot be undone.",
            onConfirm = {
                showClearDialog = false
                viewModel.clearJournals()
                SnackbarBus.tryEmit("Cleared ${journals.size} journal${if (journals.size == 1) "" else "s"}")
            },
            onDismiss = { showClearDialog = false },
        )
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            JournalOverviewCard(
                serviceRunning = serviceState.isRunning,
                logCount = logs.size,
                journalCount = journals.size,
                onStartCollection = { onServiceToggle(true) },
            )

            JournalActionRow(
                clearEnabled = journals.isNotEmpty(),
                onClear = { showClearDialog = true },
            )
        }

        JournalsList(journals)
    }
}

@Composable
private fun JournalOverviewCard(
    serviceRunning: Boolean,
    logCount: Int,
    journalCount: Int,
    onStartCollection: () -> Unit,
) {
    SurfaceCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OverviewMetricCell(
                modifier = Modifier.weight(1f),
                icon = Icons.AutoMirrored.Filled.TrendingUp,
                value = logCount.toString(),
                label = "Logs",
            )
            OverviewDivider()
            OverviewMetricCell(
                modifier = Modifier.weight(1f),
                icon = Icons.AutoMirrored.Filled.MenuBook,
                value = journalCount.toString(),
                label = "Journals",
            )
        }
        if (!serviceRunning) {
            Spacer(Modifier.height(10.dp))
            TextButton(
                onClick = onStartCollection,
                contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp),
            ) {
                Text("Start collection")
            }
        }
    }
}

@Composable
private fun OverviewMetricCell(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    value: String,
    label: String,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(22.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.headlineMedium.withSerif(),
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun OverviewDivider() {
    Box(
        modifier = Modifier
            .padding(horizontal = 10.dp)
            .width(1.dp)
            .height(48.dp)
            .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.42f))
    )
}

@Composable
private fun JournalActionRow(
    clearEnabled: Boolean,
    onClear: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.End,
    ) {
        FilledTonalIconButton(
            onClick = onClear,
            enabled = clearEnabled,
            modifier = Modifier.size(42.dp),
        ) {
            Icon(Icons.Default.DeleteOutline, contentDescription = "Clear journals")
        }
    }
}

@Composable
private fun JournalsList(journals: List<JournalEntry>) {
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
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        groupedByDay(journals.reversed()) { it.createdTimestamp }.forEach { (day, entries) ->
            item(day) {
                DaySectionHeader(day)
            }
            item("${day}_card") {
                GroupedSurfaceCard {
                    entries.forEachIndexed { index, entry ->
                        JournalEntryRow(entry)
                        if (index != entries.lastIndex) {
                            Spacer(Modifier.height(14.dp))
                            HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f))
                            Spacer(Modifier.height(14.dp))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun JournalEntryRow(entry: JournalEntry) {
    var expanded by rememberSaveable(entry.id) { mutableStateOf(false) }
    val hasError = entry.content.contains("No response", ignoreCase = true) ||
        entry.content.contains("failed", ignoreCase = true)
    val title = journalTitle(entry)
    val subtitle = journalSubtitle(entry, hasError)
    val arrowRotation by animateFloatAsState(targetValue = if (expanded) 180f else 0f, label = "arrow")

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded }
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    text = DateFormat.time(entry.createdTimestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = if (expanded) Int.MAX_VALUE else 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = if (expanded) Int.MAX_VALUE else 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(6.dp))
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                StatusPill(
                    text = if (hasError) "Failed" else "Processed",
                    color = if (hasError) MaterialTheme.colorScheme.error else AutoLifeSemantic.categoryHealth,
                )
                Icon(
                    imageVector = Icons.Default.KeyboardArrowDown,
                    contentDescription = if (expanded) "Collapse" else "Expand",
                    modifier = Modifier
                        .size(20.dp)
                        .rotate(arrowRotation),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        AnimatedVisibility(
            visible = expanded,
            enter = expandVertically(),
            exit = shrinkVertically(),
        ) {
            Column {
                Spacer(Modifier.height(12.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.28f))
                Spacer(Modifier.height(12.dp))
                if (hasError) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(
                            Icons.Default.Warning,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            text = "The generator did not return a usable summary for this window.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                }
                Text(
                    text = entry.content,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}

@Composable
private fun DaySectionHeader(label: String) {
    Text(
        text = label,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(start = 4.dp),
    )
}

@Composable
private fun GroupedSurfaceCard(
    content: @Composable ColumnScope.() -> Unit,
) {
    SurfaceCard(content = content)
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

private fun journalTitle(entry: JournalEntry): String {
    return entry.content
        .lineSequence()
        .map { it.trim() }
        .firstOrNull { it.isNotBlank() }
        ?.take(72)
        ?.ifBlank { null }
        ?: "Journal entry"
}

private fun journalSubtitle(entry: JournalEntry, hasError: Boolean): String {
    return if (hasError) {
        "Journal processing error"
    } else {
        "${DateFormat.time(entry.periodStart)} - ${DateFormat.time(entry.periodEnd)} collection window"
    }
}

private fun <T> groupedByDay(items: List<T>, timestamp: (T) -> Long): List<Pair<String, List<T>>> {
    return items.groupBy { DateFormat.monthDayYear(timestamp(it)) }.toList()
}

