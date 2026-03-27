package com.google.mediapipe.examples.llminference.ui

import android.graphics.Paint
import android.text.TextUtils
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mediapipe.examples.llminference.data.AnalysisRepository
import com.google.mediapipe.examples.llminference.network.ApplyCalendarRequest
import com.google.mediapipe.examples.llminference.network.BackendApiClient
import com.google.mediapipe.examples.llminference.ui.theme.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

// ── Data model ────────────────────────────────────────────────

data class CalendarEventBar(
    val title: String,
    val dayOfWeek: String,  // "Mon", "Tue", etc.
    val startHour: Float,
    val durationHours: Float,
    val color: Color,
    val isProposal: Boolean = false,
    val dateLabel: String = "",   // "Mon 3/25"
    val fullDate: String = ""     // "yyyy-MM-dd"
)

// ── Parsing helpers ───────────────────────────────────────────

/** Parses both ISO ("yyyy-MM-dd'T'HH:mm:ss") and space-separated ("yyyy-MM-dd HH:mm") datetime strings. */
private fun parseDateTime(s: String): Date? {
    val formats = listOf(
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm",
        "yyyy-MM-dd"
    )
    for (fmt in formats) {
        try {
            return SimpleDateFormat(fmt, Locale.getDefault()).parse(s)
        } catch (_: Exception) {}
    }
    return null
}

private fun parseDayOfWeek(startStr: String): String {
    return try {
        val date = parseDateTime(startStr) ?: return "?"
        val cal = Calendar.getInstance().apply { time = date }
        when (cal.get(Calendar.DAY_OF_WEEK)) {
            Calendar.MONDAY    -> "Mon"
            Calendar.TUESDAY   -> "Tue"
            Calendar.WEDNESDAY -> "Wed"
            Calendar.THURSDAY  -> "Thu"
            Calendar.FRIDAY    -> "Fri"
            Calendar.SATURDAY  -> "Sat"
            Calendar.SUNDAY    -> "Sun"
            else -> "?"
        }
    } catch (e: Exception) { "?" }
}

private fun parseStartHour(startStr: String): Float {
    return try {
        val date = parseDateTime(startStr) ?: return 0f
        val cal = Calendar.getInstance().apply { time = date }
        cal.get(Calendar.HOUR_OF_DAY) + cal.get(Calendar.MINUTE) / 60f
    } catch (e: Exception) { 0f }
}

private fun parseDateLabel(startStr: String): String {
    return try {
        val date = parseDateTime(startStr) ?: return ""
        SimpleDateFormat("EEE M/d", Locale.getDefault()).format(date)
    } catch (e: Exception) { "" }
}

private fun parseDateKey(startStr: String): String {
    return try {
        startStr.substring(0, 10) // "yyyy-MM-dd"
    } catch (e: Exception) { "" }
}

private fun mondayOfWeek(dateKey: String): String {
    return try {
        val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        val date = sdf.parse(dateKey) ?: return ""
        val cal = Calendar.getInstance().apply {
            firstDayOfWeek = Calendar.MONDAY
            time = date
            set(Calendar.DAY_OF_WEEK, Calendar.MONDAY)
        }
        sdf.format(cal.time)
    } catch (e: Exception) { "" }
}

private fun eventColor(title: String): Color {
    val lower = title.lowercase()
    return when {
        lower.containsAny("walk", "gym", "exercise", "health", "wellness", "meditation",
                          "yoga", "run", "therapy", "break", "rest") -> ScheduleHealth
        lower.containsAny("meet", "work", "focus", "project", "standup", "review",
                          "call", "interview", "deadline", "report")  -> ScheduleWork
        else                                                           -> ScheduleLeisure
    }
}

private fun String.containsAny(vararg keywords: String) = keywords.any { this.contains(it) }

@Suppress("UNCHECKED_CAST")
private fun buildEventBars(calendarSummary: Map<String, Any>?): List<CalendarEventBar> {
    if (calendarSummary == null) return emptyList()
    val events = (calendarSummary["events"] as? List<*>)
        ?.filterIsInstance<Map<String, Any>>()
        ?: return emptyList()

    return events.mapNotNull { event ->
        val title    = event["title"] as? String  ?: return@mapNotNull null
        val start    = event["start"] as? String  ?: return@mapNotNull null
        val duration = (event["duration_hours"] as? Double)?.toFloat() ?: 1f
        CalendarEventBar(
            title         = title,
            dayOfWeek     = parseDayOfWeek(start),
            startHour     = parseStartHour(start),
            durationHours = duration,
            color         = eventColor(title),
            dateLabel     = parseDateLabel(start),
            fullDate      = parseDateKey(start)
        )
    }
}

@Suppress("UNCHECKED_CAST")
private fun buildProposalBars(proposed: List<Map<String, Any>>): List<CalendarEventBar> {
    return proposed.mapNotNull { change ->
        val title    = change["title"] as? String      ?: return@mapNotNull null
        val startStr = change["start_time"] as? String ?: return@mapNotNull null
        val duration = (change["duration_hours"] as? Double)?.toFloat() ?: 0.5f
        CalendarEventBar(
            title         = title,
            dayOfWeek     = parseDayOfWeek(startStr),
            startHour     = parseStartHour(startStr),
            durationHours = duration,
            color         = TerminalGreen,
            isProposal    = true,
            dateLabel     = parseDateLabel(startStr),
            fullDate      = parseDateKey(startStr)
        )
    }
}

// ── Week grouping helpers ─────────────────────────────────────

private fun groupIntoWeeks(bars: List<CalendarEventBar>): List<String> {
    return bars
        .filter { it.fullDate.isNotBlank() }
        .map { mondayOfWeek(it.fullDate) }
        .filter { it.isNotBlank() }
        .distinct()
        .sorted()
}

private fun indexOfCurrentWeek(weeks: List<String>): Int {
    val todayKey = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
    val todayMonday = mondayOfWeek(todayKey)
    val idx = weeks.indexOf(todayMonday)
    return if (idx >= 0) idx else (weeks.size - 1).coerceAtLeast(0)
}

private fun filterBarsToWeek(
    bars: List<CalendarEventBar>,
    weeks: List<String>,
    weekIndex: Int
): List<CalendarEventBar> {
    if (weeks.isEmpty() || weekIndex !in weeks.indices) return bars
    val monday = weeks[weekIndex]
    return bars.filter { bar ->
        bar.fullDate.isNotBlank() && mondayOfWeek(bar.fullDate) == monday
    }
}

private fun weekLabel(weeks: List<String>, index: Int): String {
    if (weeks.isEmpty() || index !in weeks.indices) return "MON – SUN"
    return try {
        val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        val display = SimpleDateFormat("MMM d", Locale.getDefault())
        val monday = sdf.parse(weeks[index]) ?: return "MON – SUN"
        val cal = Calendar.getInstance().apply { time = monday }
        val monStr = display.format(cal.time)
        cal.add(Calendar.DAY_OF_YEAR, 6)
        val sunStr = display.format(cal.time)
        "$monStr – $sunStr"
    } catch (e: Exception) { "MON – SUN" }
}

// ── Category hours helper ─────────────────────────────────────

private data class CategoryHours(val work: Float, val health: Float, val leisure: Float)

private fun categoryHours(bars: List<CalendarEventBar>): CategoryHours {
    var work = 0f; var health = 0f; var leisure = 0f
    bars.filter { !it.isProposal }.forEach { bar ->
        when (bar.color) {
            ScheduleWork    -> work += bar.durationHours
            ScheduleHealth  -> health += bar.durationHours
            else            -> leisure += bar.durationHours
        }
    }
    return CategoryHours(work, health, leisure)
}

// ── Conflict detection helpers ────────────────────────────────

private fun proposalKey(change: Map<String, Any>): String {
    val title = change["title"] as? String ?: ""
    val start = change["start_time"] as? String ?: ""
    // Key on date portion only (yyyy-MM-dd) so ISO and space-separated formats both match
    return "$title|${start.take(10)}"
}

private fun hasConflict(proposal: CalendarEventBar, existing: List<CalendarEventBar>): Boolean {
    val sameDayEvents = existing.filter { !it.isProposal && it.fullDate == proposal.fullDate }
    val pStart = proposal.startHour
    val pEnd   = pStart + proposal.durationHours
    return sameDayEvents.any { event ->
        val eStart = event.startHour
        val eEnd   = eStart + event.durationHours
        pStart < eEnd - 0.01f && eStart < pEnd - 0.01f
    }
}

// ── ViewModel ─────────────────────────────────────────────────

class ScheduleViewModel : ViewModel() {
    private val repo = AnalysisRepository
    var applyStatus by mutableStateOf<String?>(null)
    var isApplying  by mutableStateOf(false)

    fun applySelected() {
        if (repo.selectedProposals.isEmpty()) return
        viewModelScope.launch {
            isApplying = true
            applyStatus = null
            try {
                val request = ApplyCalendarRequest(changes = repo.selectedProposals.toList())
                val response = BackendApiClient.apiService.applyCalendar(request)
                applyStatus = "applied: ${response.applied.size}  failed: ${response.failed.size}"
                val applied = repo.selectedProposals.toList()
                repo.setResult(
                    repo.result.value?.copy(
                        proposed_changes = repo.result.value!!.proposed_changes.filter { it !in applied }
                    )
                )
                repo.selectedProposals.clear()
            } catch (e: Exception) {
                applyStatus = "err: ${e.message}"
            } finally {
                isApplying = false
            }
        }
    }
}

// ── Screen ────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleScreen(viewModel: ScheduleViewModel = viewModel()) {
    val result by AnalysisRepository.result.collectAsStateWithLifecycle()

    if (result == null) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(DarkBackground),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("NO DATA", style = MaterialTheme.typography.titleLarge, color = DarkOnSurfaceDim)
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Run analysis from the AGENT tab to see your weekly schedule.",
                    style = MaterialTheme.typography.labelMedium,
                    color = DarkOnSurfaceDim
                )
            }
        }
        return
    }

    val calSummary   = result!!.calendar_summary
    val eventBars    = remember(result) { buildEventBars(calSummary) }
    val proposalBars = remember(result) { buildProposalBars(result!!.proposed_changes) }

    // Week navigation
    val allWeeks = remember(eventBars, proposalBars) { groupIntoWeeks(eventBars + proposalBars) }
    var currentWeekIndex by remember(allWeeks) { mutableIntStateOf(indexOfCurrentWeek(allWeeks)) }
    val weekRangeLabel = remember(allWeeks, currentWeekIndex) { weekLabel(allWeeks, currentWeekIndex) }

    // Category filters
    var showWork    by remember { mutableStateOf(true) }
    var showHealth  by remember { mutableStateOf(true) }
    var showLeisure by remember { mutableStateOf(true) }

    // Filter bars by visibility
    val visibleBars = remember(eventBars, proposalBars, showWork, showHealth, showLeisure) {
        (eventBars + proposalBars).filter { bar ->
            when {
                bar.isProposal            -> true
                bar.color == ScheduleWork    -> showWork
                bar.color == ScheduleHealth  -> showHealth
                else                         -> showLeisure
            }
        }
    }

    // Bars for current week
    val weekBars = remember(visibleBars, allWeeks, currentWeekIndex) {
        filterBarsToWeek(visibleBars, allWeeks, currentWeekIndex)
    }

    // Category hours for current week (all, not filtered)
    val weekAllBars = remember(eventBars, proposalBars, allWeeks, currentWeekIndex) {
        filterBarsToWeek(eventBars + proposalBars, allWeeks, currentWeekIndex)
    }
    val catHours = remember(weekAllBars) { categoryHours(weekAllBars) }

    @Suppress("UNCHECKED_CAST")
    val totalHours = (calSummary?.get("total_hours") as? Double)?.let { "%.1f".format(it) } ?: "─"
    @Suppress("UNCHECKED_CAST")
    val busiestDay = (calSummary?.get("busiest_day") as? String) ?: "─"

    // Event detail bottom sheet
    var selectedBar by remember { mutableStateOf<CalendarEventBar?>(null) }

    // Expandable proposals
    val expandedProposals = remember { mutableStateListOf<String>() }
    val conflictFlags = remember(proposalBars, eventBars) {
        proposalBars.associateWith { hasConflict(it, eventBars) }
    }

    // Week monday key for chart
    val weekMondayKey = if (allWeeks.isNotEmpty() && currentWeekIndex in allWeeks.indices)
        allWeeks[currentWeekIndex] else ""

    Box(modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(DarkBackground)
                .padding(horizontal = 12.dp),
            contentPadding = PaddingValues(vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // ── Header ───────────────────────────────────────────
            item {
                TerminalCard(accentColor = TerminalBlue) {
                    Text(
                        "WEEKLY SCHEDULE OUTPUT",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    MonoRow("total_hours", totalHours)
                    MonoRow("busiest_day", busiestDay)
                    MonoRow("events", "${eventBars.size}  proposals: ${proposalBars.size}")
                    MonoRow("work_h", "%.1fh".format(catHours.work), valueColor = ScheduleWork)
                    MonoRow("health_h", "%.1fh".format(catHours.health), valueColor = ScheduleHealth)
                    MonoRow("leisure_h", "%.1fh".format(catHours.leisure), valueColor = ScheduleLeisure)
                }
            }

            // ── Filter chips ─────────────────────────────────────
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    CategoryFilterChip("Work", ScheduleWork, showWork) { showWork = it }
                    CategoryFilterChip("Health", ScheduleHealth, showHealth) { showHealth = it }
                    CategoryFilterChip("Leisure", ScheduleLeisure, showLeisure) { showLeisure = it }
                }
            }

            // ── Week navigation ──────────────────────────────────
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    IconButton(
                        onClick = { currentWeekIndex-- },
                        enabled = currentWeekIndex > 0
                    ) {
                        Icon(
                            Icons.Default.ChevronLeft,
                            contentDescription = "Previous week",
                            tint = if (currentWeekIndex > 0) DarkOnSurface else DarkBorder
                        )
                    }
                    Text(
                        weekRangeLabel,
                        style = MaterialTheme.typography.labelLarge,
                        color = DarkOnSurface,
                        fontWeight = FontWeight.Bold
                    )
                    IconButton(
                        onClick = { currentWeekIndex++ },
                        enabled = currentWeekIndex < allWeeks.size - 1
                    ) {
                        Icon(
                            Icons.Default.ChevronRight,
                            contentDescription = "Next week",
                            tint = if (currentWeekIndex < allWeeks.size - 1) DarkOnSurface else DarkBorder
                        )
                    }
                }
            }

            // ── Week bar chart ───────────────────────────────────
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(2.dp),
                    colors = CardDefaults.cardColors(containerColor = DarkSurface),
                    border = BorderStroke(1.dp, DarkBorder)
                ) {
                    Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
                        WeekBarChart(
                            bars = weekBars,
                            weekMondayKey = weekMondayKey,
                            onBarClick = { selectedBar = it }
                        )
                    }
                }
            }

            // ── Legend ───────────────────────────────────────────
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 56.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    LegendItem("Work",    ScheduleWork)
                    LegendItem("Health",  ScheduleHealth)
                    LegendItem("Leisure", ScheduleLeisure)
                    LegendItem("AI Proposal", TerminalGreen)
                }
            }

            // ── AI Proposals ─────────────────────────────────────
            if (result!!.proposed_changes.isNotEmpty()) {
                item { SectionHeader("AI PROPOSALS") }

                items(result!!.proposed_changes) { change ->
                    val isSelected = AnalysisRepository.selectedProposals.contains(change)
                    val pKey = proposalKey(change)
                    val bar = proposalBars.find {
                        "${it.title}|${it.fullDate}" == pKey
                    }
                    val conflict = bar?.let { conflictFlags[it] } ?: false
                    val isExpanded = expandedProposals.contains(pKey)
                    ProposalRow(
                        change = change,
                        isSelected = isSelected,
                        hasConflict = conflict,
                        isExpanded = isExpanded,
                        onToggleExpand = {
                            if (isExpanded) expandedProposals.remove(pKey)
                            else expandedProposals.add(pKey)
                        }
                    )
                }

                item {
                    Spacer(modifier = Modifier.height(4.dp))
                    if (viewModel.applyStatus != null) {
                        Text(
                            viewModel.applyStatus!!,
                            style = MaterialTheme.typography.labelMedium,
                            color = if (viewModel.applyStatus!!.startsWith("err")) TerminalRed else TerminalGreen,
                            modifier = Modifier.padding(bottom = 6.dp)
                        )
                    }
                    OutlinedButton(
                        onClick = { viewModel.applySelected() },
                        enabled = AnalysisRepository.selectedProposals.isNotEmpty() && !viewModel.isApplying,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(2.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = ToolCalendar),
                        border = BorderStroke(
                            1.dp,
                            if (AnalysisRepository.selectedProposals.isNotEmpty()) ToolCalendar else DarkBorder
                        )
                    ) {
                        Text(
                            if (viewModel.isApplying) "█  APPLYING..."
                            else "▶  APPLY SELECTED TO CALENDAR (${AnalysisRepository.selectedProposals.size})",
                            style = MaterialTheme.typography.labelLarge
                        )
                    }
                }
            }
        }

        // ── Event detail bottom sheet ────────────────────────
        if (selectedBar != null) {
            EventDetailSheet(
                bar = selectedBar!!,
                onDismiss = { selectedBar = null }
            )
        }
    }
}

// ── Category filter chip ─────────────────────────────────────

@Composable
private fun CategoryFilterChip(
    label: String,
    chipColor: Color,
    selected: Boolean,
    onSelectedChange: (Boolean) -> Unit
) {
    FilterChip(
        selected = selected,
        onClick = { onSelectedChange(!selected) },
        label = {
            Text(label, style = MaterialTheme.typography.labelSmall)
        },
        leadingIcon = {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(chipColor, CircleShape)
            )
        },
        shape = RoundedCornerShape(2.dp),
        border = FilterChipDefaults.filterChipBorder(
            enabled = true,
            selected = selected,
            borderColor = DarkBorder,
            selectedBorderColor = chipColor
        ),
        colors = FilterChipDefaults.filterChipColors(
            containerColor = DarkSurface,
            selectedContainerColor = DarkSurfaceVar,
            labelColor = DarkOnSurfaceDim,
            selectedLabelColor = DarkOnSurface
        )
    )
}

// ── Lane assignment for overlapping events ───────────────────

/** Hit rectangle for tap detection on event bars. */
private data class BarHitRect(val startX: Float, val endX: Float, val topY: Float, val bottomY: Float)

/**
 * Assigns events to non-overlapping vertical lanes using greedy interval packing.
 * Returns a map from event index to lane number (0-based).
 */
private fun assignLanes(events: List<CalendarEventBar>): Map<Int, Int> {
    val laneEnds = mutableListOf<Float>()   // laneEnds[i] = endHour of last event in lane i
    val assignment = mutableMapOf<Int, Int>()
    val sorted = events.indices.sortedBy { events[it].startHour }
    for (idx in sorted) {
        val ev = events[idx]
        val startH = ev.startHour
        val lane = laneEnds.indexOfFirst { it <= startH }
        if (lane >= 0) {
            laneEnds[lane] = startH + ev.durationHours
            assignment[idx] = lane
        } else {
            assignment[idx] = laneEnds.size
            laneEnds.add(startH + ev.durationHours)
        }
    }
    return assignment
}

// ── Weekly bar chart ──────────────────────────────────────────

private val DAYS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
private const val DAY_START = 6f   // 6 AM
private const val DAY_END   = 22f  // 10 PM
private const val HOUR_SPAN = DAY_END - DAY_START  // 16 hours

@Composable
private fun WeekBarChart(
    bars: List<CalendarEventBar>,
    weekMondayKey: String,
    onBarClick: (CalendarEventBar) -> Unit
) {
    val byDay = bars.groupBy { it.dayOfWeek }

    // Build day display labels from Monday key
    val dayDisplayLabels = remember(weekMondayKey) {
        if (weekMondayKey.isBlank()) {
            DAYS.associateWith { it }
        } else {
            try {
                val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
                val display = SimpleDateFormat("M/d", Locale.getDefault())
                val monday = sdf.parse(weekMondayKey)!!
                val cal = Calendar.getInstance().apply { time = monday }
                DAYS.associateWith { day ->
                    val label = "$day ${display.format(cal.time)}"
                    cal.add(Calendar.DAY_OF_YEAR, 1)
                    label
                }
            } catch (e: Exception) {
                DAYS.associateWith { it }
            }
        }
    }

    // Find today's day name
    val todayName = remember {
        SimpleDateFormat("EEE", Locale.getDefault())
            .format(Date())
            .replaceFirstChar { c -> c.uppercaseChar() }
            .take(3)
    }
    val todayMonday = remember { mondayOfWeek(SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())) }
    val isCurrentWeek = weekMondayKey == todayMonday

    Column {
        // Hour axis
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 56.dp, bottom = 2.dp)
        ) {
            val hours = listOf(6, 9, 12, 15, 18, 21, 22)
            hours.zipWithNext().forEach { (h1, h2) ->
                Text(
                    if (h1 < 10) "0$h1" else "$h1",
                    style = MaterialTheme.typography.labelSmall,
                    color = DarkOnSurfaceDim,
                    modifier = Modifier.weight((h2 - h1).toFloat())
                )
            }
        }

        // Day rows
        DAYS.forEach { day ->
            val isToday = isCurrentWeek && day == todayName
            DayRow(
                dayLabel = day,
                dayDisplayLabel = dayDisplayLabels[day] ?: day,
                events = byDay[day] ?: emptyList(),
                isToday = isToday,
                onBarClick = onBarClick
            )
        }
    }
}

@Composable
private fun DayRow(
    dayLabel: String,
    dayDisplayLabel: String,
    events: List<CalendarEventBar>,
    isToday: Boolean,
    onBarClick: (CalendarEventBar) -> Unit
) {
    val density = LocalDensity.current.density

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(26.dp)
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            if (isToday) "▶ $dayDisplayLabel" else dayDisplayLabel,
            style = MaterialTheme.typography.labelSmall,
            color = if (isToday) TerminalGreen else DarkOnSurfaceDim,
            fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal,
            modifier = Modifier.width(52.dp),
            maxLines = 1
        )
        // Track bar positions for tap detection
        val barPositions = remember(events) { mutableListOf<Pair<Float, Float>>() }

        Canvas(
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight()
                .pointerInput(events) {
                    detectTapGestures { offset ->
                        val tappedIndex = barPositions.indexOfFirst { (startX, endX) ->
                            offset.x in startX..endX
                        }
                        if (tappedIndex in events.indices) {
                            onBarClick(events[tappedIndex])
                        }
                    }
                }
        ) {
            barPositions.clear()

            // Grid lines at 3h intervals
            listOf(0f, 3f, 6f, 9f, 12f, 15f).forEach { offset ->
                val x = (offset / HOUR_SPAN) * size.width
                drawLine(
                    color = Color(0xFF2A2A2A),
                    start = Offset(x, 0f),
                    end   = Offset(x, size.height),
                    strokeWidth = 1f
                )
            }
            // Event bars
            val barH   = size.height * 0.65f
            val barTop = (size.height - barH) / 2f
            events.forEach { event ->
                val startX = ((event.startHour - DAY_START).coerceAtLeast(0f) / HOUR_SPAN * size.width)
                val barW   = (event.durationHours.coerceIn(0.05f, HOUR_SPAN) / HOUR_SPAN * size.width)
                    .coerceAtLeast(4f)
                barPositions.add(startX to (startX + barW))

                drawRoundRect(
                    color        = event.color.copy(alpha = if (event.isProposal) 0.55f else 0.85f),
                    topLeft      = Offset(startX, barTop),
                    size         = Size(barW, barH),
                    cornerRadius = CornerRadius(2f)
                )

                // Draw title label if bar is wide enough
                if (barW > 60f * density) {
                    val textPaint = Paint().apply {
                        color = android.graphics.Color.WHITE
                        textSize = 9f * density
                        isAntiAlias = true
                    }
                    val maxTextWidth = barW - 4f * density
                    val ellipsized = TextUtils.ellipsize(
                        event.title,
                        android.text.TextPaint(textPaint),
                        maxTextWidth,
                        TextUtils.TruncateAt.END
                    ).toString()

                    drawContext.canvas.nativeCanvas.save()
                    drawContext.canvas.nativeCanvas.clipRect(
                        startX, barTop, startX + barW, barTop + barH
                    )
                    drawContext.canvas.nativeCanvas.drawText(
                        ellipsized,
                        startX + 2f * density,
                        barTop + barH * 0.75f,
                        textPaint
                    )
                    drawContext.canvas.nativeCanvas.restore()
                }
            }
        }
    }
}

// ── Event detail bottom sheet ─────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EventDetailSheet(bar: CalendarEventBar, onDismiss: () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = DarkSurface,
        contentColor = DarkOnSurface
    ) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .background(bar.color, CircleShape)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    bar.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            MonoRow("date", bar.dateLabel.ifBlank { bar.dayOfWeek })
            MonoRow("start", "%02d:%02d".format(bar.startHour.toInt(), ((bar.startHour % 1) * 60).toInt()))
            MonoRow("duration", "%.1fh".format(bar.durationHours))
            MonoRow("type", when {
                bar.isProposal           -> "AI Proposal"
                bar.color == ScheduleWork    -> "Work"
                bar.color == ScheduleHealth  -> "Health"
                else                         -> "Leisure"
            })
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

// ── Helpers ───────────────────────────────────────────────────

@Composable
private fun LegendItem(label: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(color, RoundedCornerShape(1.dp))
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = DarkOnSurfaceDim)
    }
}

@Composable
private fun ProposalRow(
    change: Map<String, Any>,
    isSelected: Boolean,
    hasConflict: Boolean,
    isExpanded: Boolean,
    onToggleExpand: () -> Unit
) {
    @Suppress("UNCHECKED_CAST")
    val title    = change["title"] as? String ?: "Untitled"
    val startStr = change["start_time"] as? String ?: ""
    val desc     = change["description"] as? String

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) Color(0xFF0D1F0D) else DarkSurface
        ),
        border = BorderStroke(1.dp, if (isSelected) TerminalGreen else DarkBorder)
    ) {
        Row(
            modifier = Modifier.padding(10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(
                checked = isSelected,
                onCheckedChange = { checked ->
                    if (checked) AnalysisRepository.selectedProposals.add(change)
                    else         AnalysisRepository.selectedProposals.remove(change)
                },
                colors = CheckboxDefaults.colors(
                    checkedColor   = TerminalGreen,
                    uncheckedColor = DarkOnSurfaceDim
                )
            )
            Column(modifier = Modifier
                .padding(start = 8.dp)
                .weight(1f)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "[ADD]  $title",
                        style = MaterialTheme.typography.labelLarge,
                        color = if (isSelected) TerminalGreen else DarkOnSurface,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f)
                    )
                }
                if (startStr.isNotBlank()) {
                    Text(
                        "time: $startStr",
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                }
                if (hasConflict) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.Warning,
                            contentDescription = "Conflict",
                            tint = TerminalAmber,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            "⚠ overlaps existing event",
                            style = MaterialTheme.typography.labelSmall,
                            color = TerminalAmber
                        )
                    }
                }
                if (isExpanded && !desc.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        desc,
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                }
            }
            if (!desc.isNullOrBlank()) {
                IconButton(
                    onClick = onToggleExpand,
                    modifier = Modifier.size(24.dp)
                ) {
                    Icon(
                        if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = if (isExpanded) "Collapse" else "Expand",
                        tint = DarkOnSurfaceDim,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
        }
    }
}
