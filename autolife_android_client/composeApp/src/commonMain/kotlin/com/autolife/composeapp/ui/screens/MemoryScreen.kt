package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Timeline
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import com.autolife.composeapp.ui.components.withSerif
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.ui.components.ActionableEmptyState
import com.autolife.composeapp.ui.components.ErrorCard
import com.autolife.composeapp.ui.components.MutedDivider
import com.autolife.composeapp.ui.components.SkeletonCard
import com.autolife.composeapp.ui.components.SectionHeader
import com.autolife.composeapp.ui.components.SurfaceCard
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.HealthHistoryEntry
import com.autolife.shared.model.UserMemoryData
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.platform.currentTimeMillis
import com.autolife.shared.repository.AnalysisRepository
import kotlinx.coroutines.launch

// ─── ViewModel ───────────────────────────────────────────────────────────────

class MemoryViewModel : ViewModel() {
    var isLoading by mutableStateOf(false)
        private set
    var fetchError by mutableStateOf<String?>(null)
        private set
    var lastRefreshedMs by mutableStateOf<Long?>(null)
        private set

    init { fetch() }

    fun fetch() {
        viewModelScope.launch {
            isLoading = true
            fetchError = null
            try {
                val data = AutoLifeApi.getMemory(AnalysisRepository.userId)
                AnalysisRepository.setMemory(data)
                lastRefreshedMs = currentTimeMillis()
            } catch (e: Exception) {
                fetchError = e.message
            } finally {
                isLoading = false
            }
        }
    }
}

// ─── Screen ──────────────────────────────────────────────────────────────────

@Composable
fun MemoryScreen(viewModel: MemoryViewModel = viewModel { MemoryViewModel() }) {
    val memory by AnalysisRepository.memory.collectAsState()

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            MemoryPageIntro(
                isLoading = viewModel.isLoading,
                lastRefreshedMs = viewModel.lastRefreshedMs,
                onRefresh = { viewModel.fetch() },
            )
        }

        if (viewModel.fetchError != null) {
            item {
                ErrorCard(
                    title = "Couldn't load memory",
                    message = "We couldn't reach the backend. Retry when you're ready.",
                    details = viewModel.fetchError,
                    onRetry = { viewModel.fetch() },
                )
            }
        }

        if (memory == null && viewModel.isLoading) {
            item { SkeletonCard(height = 110) }
            item { SkeletonCard(height = 220) }
            return@LazyColumn
        }

        if (memory == null && !viewModel.isLoading) {
            item {
                SurfaceCard {
                    ActionableEmptyState(
                        icon = Icons.Default.Storage,
                        title = if (viewModel.fetchError == null) "No memory data yet"
                                else "Memory is unavailable",
                        description = if (viewModel.fetchError == null)
                            "Run analysis to build personalized preferences and wellbeing history."
                        else
                            "The backend could not be reached. Retry when the connection is available.",
                        action = {
                            Button(onClick = { viewModel.fetch() }) { Text("Refresh") }
                        },
                    )
                }
            }
            return@LazyColumn
        }

        memory?.let { mem ->
            val prefs = mem.preferences
            val health = mem.health
            val learnedStatements = buildLearnedStatements(mem)
            val hasPreferences = learnedStatements.isNotEmpty()
            val hasHistory = health.history.isNotEmpty()
            val hasFeedbackPatterns = hasSuggestionFeedback(mem)

            item {
                MemoryHonestyCard(
                    hasPreferences = hasPreferences,
                    hasHistory = hasHistory,
                    lastRefreshedMs = viewModel.lastRefreshedMs,
                )
            }

            if (hasPreferences) {
                item {
                    MemorySection(
                        icon = Icons.Default.CheckCircle,
                        title = "Learned from feedback",
                        subtitle = "Only explicit preference signals are shown here."
                    ) {
                        learnedStatements.forEachIndexed { index, statement ->
                            MemoryStatementRow(statement = statement)
                            if (index != learnedStatements.lastIndex) {
                                MutedDivider(Modifier.padding(top = 12.dp))
                            }
                        }
                    }
                }
            }

            if (hasHistory) {
                item {
                    MemorySection(
                        icon = Icons.Default.Timeline,
                        title = "Wellbeing over time",
                        subtitle = "Recorded after each completed analysis."
                    ) {
                        WellbeingHistorySection(
                            riskLevel = health.risk_level,
                            trend = health.trend,
                            history = health.history,
                        )
                    }
                }
            } else {
                item {
                    SurfaceCard {
                        Text(
                            text = "No recorded wellbeing history yet",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = "Run an analysis to start building a real trend instead of placeholder memory.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            if (hasFeedbackPatterns) {
                item {
                    MemorySection(
                        icon = Icons.Default.Tune,
                        title = "Response patterns",
                        subtitle = "How your recent schedule suggestions have landed."
                    ) {
                        SuggestionFeedbackSection(mem)
                    }
                }
            }

            if (!hasPreferences && !hasHistory && !hasFeedbackPatterns) {
                item {
                    SurfaceCard {
                        Text(
                            text = "Memory is still being built.",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = "Once you give feedback or complete more analyses, this page will fill in with confirmed preferences and a real trend line.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SuggestionFeedbackSection(memory: UserMemoryData) {
    val accepted = memory.feedback.accepted_suggestions
    val rejected = memory.feedback.rejected_suggestions
    val total = accepted.size + rejected.size
    val recentAccepted = accepted.takeLast(2).reversed()
    val recentRejected = rejected.takeLast(2).reversed()

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        WellbeingSummaryCard(
            title = "Accepted",
            mainText = accepted.size.toString(),
            supportingText = feedbackRatioText(accepted.size, total),
            accent = MaterialTheme.colorScheme.secondary,
            modifier = Modifier.weight(1f),
        )
        WellbeingSummaryCard(
            title = "Passed on",
            mainText = rejected.size.toString(),
            supportingText = if (rejected.isEmpty()) "No recent skips" else "Suggestions not applied",
            accent = MaterialTheme.colorScheme.error,
            modifier = Modifier.weight(1f),
        )
    }

    if (recentAccepted.isNotEmpty()) {
        Spacer(Modifier.height(14.dp))
        SectionHeader(title = "Recently accepted")
        recentAccepted.forEachIndexed { index, entry ->
            SuggestionFeedbackRow(entry = entry, tone = "Accepted")
            if (index != recentAccepted.lastIndex) {
                MutedDivider(Modifier.padding(top = 10.dp))
            }
        }
    }

    if (recentRejected.isNotEmpty()) {
        Spacer(Modifier.height(14.dp))
        SectionHeader(title = "Recently skipped")
        recentRejected.forEachIndexed { index, entry ->
            SuggestionFeedbackRow(entry = entry, tone = "Skipped")
            if (index != recentRejected.lastIndex) {
                MutedDivider(Modifier.padding(top = 10.dp))
            }
        }
    }
}

@Composable
private fun MemoryPageIntro(
    isLoading: Boolean,
    lastRefreshedMs: Long?,
    onRefresh: () -> Unit,
) {
    SurfaceCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    text = "Memory",
                    style = MaterialTheme.typography.headlineMedium.withSerif(),
                    color = MaterialTheme.colorScheme.onBackground,
                )
                Text(
                    text = "A quiet record of what the system actually knows so far.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (lastRefreshedMs != null) {
                    Text(
                        text = "Last synced ${formatTime(lastRefreshedMs)}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            TextButton(
                onClick = onRefresh,
                enabled = !isLoading,
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                }
                Spacer(Modifier.width(6.dp))
                Text(if (isLoading) "Refreshing" else "Refresh")
            }
        }
    }
}

@Composable
private fun MemoryHonestyCard(
    hasPreferences: Boolean,
    hasHistory: Boolean,
    lastRefreshedMs: Long?,
) {
    SurfaceCard(
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = "Shown here",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = honestyLine(hasPreferences, hasHistory),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        if (lastRefreshedMs != null) {
            Spacer(Modifier.height(10.dp))
            Text(
                text = "Synced at ${formatTime(lastRefreshedMs)}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun MemorySection(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    content: @Composable ColumnScope.() -> Unit,
) {
    SurfaceCard {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(20.dp),
            )
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(14.dp))
        content()
    }
}

@Composable
private fun MemoryStatementRow(statement: String) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = statement,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            text = "Confirmed from direct feedback",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun WellbeingHistorySection(
    riskLevel: String,
    trend: String,
    history: List<HealthHistoryEntry>,
) {
    val historyCount = history.size
    val recentEntries = history.takeLast(3).reversed()

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        WellbeingSummaryCard(
            title = "Latest",
            mainText = riskLevel.replaceFirstChar { it.uppercase() }.ifBlank { "Unknown" },
            supportingText = riskLevelSubtitle(riskLevel),
            accent = AutoLifeSemantic.riskColor(riskLevel),
            modifier = Modifier.weight(1f),
        )
        WellbeingSummaryCard(
            title = "Trend",
            mainText = trendLabel(trend),
            supportingText = if (historyCount < 3) "Still early" else "$historyCount entries tracked",
            accent = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(1f),
        )
    }

    Spacer(Modifier.height(14.dp))

    Text(
        text = "Trend line",
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(8.dp))
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.22f),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.2f)),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            WellbeingSparkline(
                history = history,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = sparklineCaption(historyCount),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (recentEntries.isNotEmpty()) {
        Spacer(Modifier.height(14.dp))
        SectionHeader(title = "Recent check-ins")
        recentEntries.forEachIndexed { index, entry ->
            RecentMemoryEntryRow(entry = entry)
            if (index != recentEntries.lastIndex) {
                MutedDivider(Modifier.padding(top = 10.dp))
            }
        }
    }
}

@Composable
private fun WellbeingSummaryCard(
    title: String,
    mainText: String,
    supportingText: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .background(
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.22f),
                shape = RoundedCornerShape(12.dp),
            )
            .padding(horizontal = 12.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = mainText,
            style = MaterialTheme.typography.titleLarge.withSerif(),
            color = accent,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = supportingText,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun RecentMemoryEntryRow(
    entry: HealthHistoryEntry,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = formatHistoryTimestamp(entry.timestamp),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = "Recorded wellbeing assessment",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            text = entry.risk_level.replaceFirstChar { it.uppercase() }.ifBlank { "Unknown" },
            style = MaterialTheme.typography.titleMedium,
            color = AutoLifeSemantic.riskColor(entry.risk_level),
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun SuggestionFeedbackRow(
    entry: com.autolife.shared.model.SuggestionFeedbackEntry,
    tone: String,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = entry.suggestion.ifBlank { "Untitled suggestion" },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.Medium,
            )
            val supporting = listOf(
                tone,
                entry.behavioral_state_summary.takeIf { it.isNotBlank() },
                formatHistoryTimestamp(entry.timestamp),
            ).joinToString(" · ")
            Text(
                text = supporting,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun WellbeingSparkline(
    history: List<HealthHistoryEntry>,
    modifier: Modifier = Modifier,
) {
    val lineColor = MaterialTheme.colorScheme.secondary
    val dotColor  = MaterialTheme.colorScheme.secondary
    val fillColor = MaterialTheme.colorScheme.secondary.copy(alpha = 0.08f)
    val emptyLineColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f)

    val normalised = history.takeLast(7).map { riskToFloat(it.risk_level) }

    Canvas(modifier = modifier) {
        if (normalised.isEmpty()) {
            val midY = size.height / 2
            drawLine(
                color = emptyLineColor,
                start = Offset(0f, midY),
                end = Offset(size.width, midY),
                strokeWidth = 2.dp.toPx(),
                cap = StrokeCap.Round,
            )
            return@Canvas
        }

        val w = size.width
        val h = size.height
        val stepX = if (normalised.size > 1) w / (normalised.size - 1).toFloat() else w
        val points = normalised.mapIndexed { i, v ->
            Offset(i * stepX, h - v * h * 0.85f - h * 0.075f)
        }

        // Fill path
        val fillPath = Path().apply {
            moveTo(points.first().x, h)
            points.forEach { lineTo(it.x, it.y) }
            lineTo(points.last().x, h)
            close()
        }
        drawPath(fillPath, color = fillColor)

        // Line path
        val linePath = Path().apply {
            points.forEachIndexed { i, pt ->
                if (i == 0) moveTo(pt.x, pt.y) else lineTo(pt.x, pt.y)
            }
        }
        drawPath(
            linePath,
            color = lineColor,
            style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round),
        )

        // Dots
        points.forEach { pt ->
            drawCircle(color = dotColor, radius = 3.dp.toPx(), center = pt)
            drawCircle(
                color = Color.White,
                radius = 1.5.dp.toPx(),
                center = pt,
            )
        }
    }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Formats epoch milliseconds to HH:MM. */
private fun formatTime(epochMs: Long): String {
    val totalSeconds = epochMs / 1000
    val totalMinutes = totalSeconds / 60
    val hours        = (totalMinutes / 60) % 24
    val minutes      = totalMinutes % 60
    return "${padTwo(hours.toInt())}:${padTwo(minutes.toInt())}"
}

private fun padTwo(n: Int): String = if (n < 10) "0$n" else "$n"

/** Maps a risk level string to a normalised float for the sparkline (0 = best, 1 = worst). */
private fun riskToFloat(level: String): Float = when (level.lowercase()) {
    "low", "minimal"  -> 0.15f
    "mild"            -> 0.40f
    "moderate"        -> 0.65f
    "severe", "high"  -> 0.90f
    else              -> 0.30f
}

private fun buildLearnedStatements(memory: UserMemoryData): List<String> {
    val prefs = memory.preferences
    val items = mutableListOf<String>()
    items += prefs.explicit_preferences.filter { it.isNotBlank() }
    if (prefs.disliked_activities.isNotEmpty()) {
        items += "Avoids ${prefs.disliked_activities.joinToString(", ")}"
    }
    if (prefs.preferred_activities.isNotEmpty()) {
        items += "Prefers ${prefs.preferred_activities.joinToString(", ")}"
    }
    return items.distinct()
}

private fun hasSuggestionFeedback(memory: UserMemoryData): Boolean {
    return memory.feedback.accepted_suggestions.isNotEmpty() ||
        memory.feedback.rejected_suggestions.isNotEmpty()
}

private fun honestyLine(hasPreferences: Boolean, hasHistory: Boolean): String = when {
    hasPreferences && hasHistory ->
        "Confirmed feedback and recorded wellbeing history."
    hasPreferences ->
        "Confirmed feedback only. Trend history is still building."
    hasHistory ->
        "Recorded wellbeing history only. No explicit preferences have been confirmed yet."
    else ->
        "No confirmed memory yet. This page stays sparse until something real is learned."
}

private fun trendLabel(trend: String): String = when (trend.lowercase()) {
    "rising" -> "Rising"
    "falling" -> "Falling"
    "stable" -> "Stable"
    "insufficient_data" -> "Too early"
    else -> "Unknown"
}

private fun sparklineCaption(historyCount: Int): String = when {
    historyCount >= 7 -> "Based on the most recent 7 assessments."
    historyCount >= 2 -> "Based on $historyCount recorded assessments."
    historyCount == 1 -> "Only one assessment recorded so far."
    else -> "Run analysis to begin a real trend line."
}

private fun feedbackRatioText(count: Int, total: Int): String = when {
    total <= 0 -> "No response pattern yet"
    count == 0 -> "None recently"
    else -> "$count of $total recent suggestions"
}

private fun formatHistoryTimestamp(timestamp: String): String {
    if (timestamp.length >= 16) {
        val date = timestamp.substring(0, 10)
        val time = timestamp.substring(11, 16)
        return "$date at $time"
    }
    return timestamp.ifBlank { "Unknown time" }
}

/** Human-readable subtitle for a risk level. */
private fun riskLevelSubtitle(level: String): String = when (level.lowercase()) {
    "low", "minimal"  -> "Looking good"
    "mild"            -> "Monitor closely"
    "moderate"        -> "Take action"
    "severe", "high"  -> "Needs attention"
    else              -> "Insufficient history"
}
