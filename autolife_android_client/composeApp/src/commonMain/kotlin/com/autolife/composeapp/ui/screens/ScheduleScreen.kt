package com.autolife.composeapp.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.EventNote
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.autolife.composeapp.platform.currentDateKey
import com.autolife.composeapp.ui.DateFormat
import com.autolife.composeapp.ui.ProposalApplier
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.*
import com.autolife.shared.repository.AnalysisRepository
import kotlinx.coroutines.launch

// ── Date parsing (KMP-compatible, no java.text/java.util) ────

private data class ParsedDate(
    val year: Int, val month: Int, val day: Int,
    val hour: Int = 0, val minute: Int = 0,
)

private fun parseISO(s: String): ParsedDate? {
    if (s.length < 10) return null
    val y = s.substring(0, 4).toIntOrNull() ?: return null
    val m = s.substring(5, 7).toIntOrNull() ?: return null
    val d = s.substring(8, 10).toIntOrNull() ?: return null
    if (s.length >= 16) {
        val h = s.substring(11, 13).toIntOrNull() ?: 0
        val min = s.substring(14, 16).toIntOrNull() ?: 0
        return ParsedDate(y, m, d, h, min)
    }
    return ParsedDate(y, m, d)
}

private val DOW_NAMES = arrayOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
private val MONTH_NAMES = arrayOf(
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

/** Tomohiko Sakamoto — returns 0=Sun,1=Mon,...,6=Sat */
private fun dayOfWeekIndex(y: Int, m: Int, d: Int): Int {
    val t = intArrayOf(0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    var adj = y; if (m < 3) adj--
    return ((adj + adj / 4 - adj / 100 + adj / 400 + t[m - 1] + d) % 7 + 7) % 7
}

private fun isLeapYear(y: Int) = (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0)

private fun daysInMonth(y: Int, m: Int) = when (m) {
    1, 3, 5, 7, 8, 10, 12 -> 31
    4, 6, 9, 11 -> 30
    2 -> if (isLeapYear(y)) 29 else 28
    else -> 30
}

private fun addDays(y: Int, m: Int, d: Int, n: Int): Triple<Int, Int, Int> {
    var year = y; var month = m; var day = d + n
    while (day > daysInMonth(year, month)) {
        day -= daysInMonth(year, month)
        month++; if (month > 12) { month = 1; year++ }
    }
    return Triple(year, month, day)
}

private fun subtractDays(y: Int, m: Int, d: Int, n: Int): Triple<Int, Int, Int> {
    var year = y; var month = m; var day = d - n
    while (day < 1) {
        month--; if (month < 1) { month = 12; year-- }
        day += daysInMonth(year, month)
    }
    return Triple(year, month, day)
}

private fun pad2(n: Int): String = if (n < 10) "0$n" else "$n"

private fun dateKey(y: Int, m: Int, d: Int): String {
    val yStr = y.toString().padStart(4, '0')
    return "$yStr-${pad2(m)}-${pad2(d)}"
}

private fun parseDayOfWeek(s: String): String {
    val p = parseISO(s) ?: return "?"
    return DOW_NAMES[dayOfWeekIndex(p.year, p.month, p.day)]
}

private fun parseStartHour(s: String): Float {
    val p = parseISO(s) ?: return 0f
    return p.hour + p.minute / 60f
}

private fun parseDateKey(s: String) = if (s.length >= 10) s.substring(0, 10) else ""

private fun parseDateLabel(s: String): String {
    val p = parseISO(s) ?: return ""
    val dow = DOW_NAMES[dayOfWeekIndex(p.year, p.month, p.day)]
    return "$dow ${p.month}/${p.day}"
}

private fun mondayOfWeek(key: String): String {
    val p = parseISO(key) ?: return ""
    val dow = dayOfWeekIndex(p.year, p.month, p.day) // 0=Sun..6=Sat
    val offset = (dow - 1 + 7) % 7 // days to subtract to reach Monday
    val (y, m, d) = subtractDays(p.year, p.month, p.day, offset)
    return dateKey(y, m, d)
}

private fun formatAmPm(hour: Int, minute: Int): String {
    val h = if (hour == 0) 12 else if (hour > 12) hour - 12 else hour
    val amPm = if (hour < 12) "AM" else "PM"
    return "$h:${pad2(minute)} $amPm"
}

private fun formatProposalTime(start: String, end: String?): String {
    val s = parseISO(start) ?: return start
    val dow = DOW_NAMES[dayOfWeekIndex(s.year, s.month, s.day)]
    val base = "$dow, ${MONTH_NAMES[s.month]} ${s.day} · ${formatAmPm(s.hour, s.minute)}"
    val e = if (end != null) parseISO(end) else null
    return if (e != null) "$base – ${formatAmPm(e.hour, e.minute)}" else base
}

// ── Event bar model ──────────────────────────────────────────

private data class CalendarEventBar(
    val title: String,
    val dayOfWeek: String,
    val startHour: Float,
    val durationHours: Float,
    val color: Color,
    val isProposal: Boolean = false,
    val dateLabel: String = "",
    val fullDate: String = "",
)

private fun eventColor(title: String): Color {
    val lower = title.lowercase()
    return when {
        lower.containsAny("walk", "gym", "exercise", "health", "wellness", "meditation",
            "yoga", "run", "therapy", "break", "rest") -> AutoLifeSemantic.categoryHealth
        lower.containsAny("meet", "work", "focus", "project", "standup", "review",
            "call", "interview", "deadline", "report") -> AutoLifeSemantic.categoryWork
        else -> AutoLifeSemantic.categoryLeisure
    }
}

private fun String.containsAny(vararg kw: String) = kw.any { this.contains(it) }

private fun buildEventBars(cal: CalendarSummary?): List<CalendarEventBar> {
    if (cal == null) return emptyList()
    return cal.events.mapNotNull { ev ->
        val title = ev.title.ifBlank { return@mapNotNull null }
        val start = ev.start.ifBlank { return@mapNotNull null }
        CalendarEventBar(
            title = title,
            dayOfWeek = parseDayOfWeek(start),
            startHour = parseStartHour(start),
            durationHours = ev.duration_hours.toFloat().takeIf { it > 0f } ?: 1f,
            color = eventColor(title),
            dateLabel = parseDateLabel(start),
            fullDate = parseDateKey(start),
        )
    }
}

private val proposalColor = AutoLifeSemantic.categoryHealth

private fun buildProposalBars(changes: List<ProposedChange>): List<CalendarEventBar> {
    return changes.mapNotNull { c ->
        val title = c.title ?: return@mapNotNull null
        val start = c.start_time ?: return@mapNotNull null
        val duration: Float = run {
            c.duration_hours?.toFloat()?.let { return@run it }
            val s = parseISO(start)
            val e = if (c.end_time != null) parseISO(c.end_time!!) else null
            if (s != null && e != null) {
                val sMin = s.hour * 60 + s.minute
                val eMin = e.hour * 60 + e.minute
                ((eMin - sMin) / 60f).coerceAtLeast(0.25f)
            } else 0.5f
        }
        CalendarEventBar(
            title = title,
            dayOfWeek = parseDayOfWeek(start),
            startHour = parseStartHour(start),
            durationHours = duration,
            color = proposalColor,
            isProposal = true,
            dateLabel = parseDateLabel(start),
            fullDate = parseDateKey(start),
        )
    }
}

// ── Week helpers ─────────────────────────────────────────────

private fun groupIntoWeeks(bars: List<CalendarEventBar>): List<String> =
    bars.filter { it.fullDate.isNotBlank() }
        .map { mondayOfWeek(it.fullDate) }
        .filter { it.isNotBlank() }
        .distinct().sorted()

private fun indexOfCurrentWeek(weeks: List<String>): Int {
    val today = mondayOfWeek(currentDateKey())
    val idx = weeks.indexOf(today)
    return if (idx >= 0) idx else (weeks.size - 1).coerceAtLeast(0)
}

private fun filterBarsToWeek(bars: List<CalendarEventBar>, weeks: List<String>, idx: Int): List<CalendarEventBar> {
    if (weeks.isEmpty() || idx !in weeks.indices) return bars
    val monday = weeks[idx]
    return bars.filter { it.fullDate.isNotBlank() && mondayOfWeek(it.fullDate) == monday }
}

private fun weekLabel(weeks: List<String>, idx: Int): String {
    if (weeks.isEmpty() || idx !in weeks.indices) return "Mon – Sun"
    val p = parseISO(weeks[idx]) ?: return "Mon – Sun"
    val monStr = "${MONTH_NAMES[p.month]} ${p.day}"
    val (y2, m2, d2) = addDays(p.year, p.month, p.day, 6)
    val sunStr = "${MONTH_NAMES[m2]} $d2"
    return "$monStr – $sunStr"
}

// ── Category / conflict helpers ──────────────────────────────

private data class CategoryHours(val work: Float, val health: Float, val leisure: Float)

private fun categoryHours(bars: List<CalendarEventBar>): CategoryHours {
    var w = 0f; var h = 0f; var l = 0f
    bars.filter { !it.isProposal }.forEach { b ->
        when (b.color) {
            AutoLifeSemantic.categoryWork -> w += b.durationHours
            AutoLifeSemantic.categoryHealth -> h += b.durationHours
            else -> l += b.durationHours
        }
    }
    return CategoryHours(w, h, l)
}

private fun proposalKey(c: ProposedChange) = "${c.title ?: ""}|${(c.start_time ?: "").take(10)}"

private fun hasConflict(proposal: CalendarEventBar, existing: List<CalendarEventBar>): Boolean {
    val sameDayEvents = existing.filter { !it.isProposal && it.fullDate == proposal.fullDate }
    val pStart = proposal.startHour
    val pEnd = pStart + proposal.durationHours
    return sameDayEvents.any { ev ->
        val eStart = ev.startHour; val eEnd = eStart + ev.durationHours
        pStart < eEnd - 0.01f && eStart < pEnd - 0.01f
    }
}

// ── ViewModel ────────────────────────────────────────────────

class ScheduleViewModel : ViewModel() {
    fun applySelected() {
        val current = AnalysisRepository.selectedProposals.value
        if (current.isEmpty()) return
        viewModelScope.launch { ProposalApplier.apply(current) }
    }
}

// ── Screen ───────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleScreen(viewModel: ScheduleViewModel = viewModel { ScheduleViewModel() }) {
    val result by AnalysisRepository.result.collectAsState()
    val selectedProposals by AnalysisRepository.selectedProposals.collectAsState()

    if (result == null) {
        EmptyState(
            icon = Icons.AutoMirrored.Filled.EventNote,
            title = "No Schedule Data",
            description = "Run analysis from the Agent tab to see your weekly schedule.",
        )
        return
    }

    val calSummary = result!!.calendar_summary
    val eventBars = remember(result) { buildEventBars(calSummary) }
    val proposalBars = remember(result) { buildProposalBars(result!!.proposed_changes) }

    val allWeeks = remember(eventBars, proposalBars) { groupIntoWeeks(eventBars + proposalBars) }
    var currentWeekIndex by remember(allWeeks) { mutableIntStateOf(indexOfCurrentWeek(allWeeks)) }
    val weekRangeLabel = remember(allWeeks, currentWeekIndex) { weekLabel(allWeeks, currentWeekIndex) }

    var showWork by remember { mutableStateOf(true) }
    var showHealth by remember { mutableStateOf(true) }
    var showLeisure by remember { mutableStateOf(true) }

    val visibleBars = remember(eventBars, proposalBars, showWork, showHealth, showLeisure) {
        (eventBars + proposalBars).filter { bar ->
            when {
                bar.isProposal -> true
                bar.color == AutoLifeSemantic.categoryWork -> showWork
                bar.color == AutoLifeSemantic.categoryHealth -> showHealth
                else -> showLeisure
            }
        }
    }

    val weekBars = remember(visibleBars, allWeeks, currentWeekIndex) {
        filterBarsToWeek(visibleBars, allWeeks, currentWeekIndex)
    }
    val weekAllBars = remember(eventBars, proposalBars, allWeeks, currentWeekIndex) {
        filterBarsToWeek(eventBars + proposalBars, allWeeks, currentWeekIndex)
    }
    val catHours = remember(weekAllBars) { categoryHours(weekAllBars) }

    var selectedBar by remember { mutableStateOf<CalendarEventBar?>(null) }
    val expandedProposals = remember { mutableStateListOf<String>() }
    val conflictFlags = remember(proposalBars, eventBars) {
        proposalBars.associateWith { hasConflict(it, eventBars) }
    }

    val weekMondayKey = if (allWeeks.isNotEmpty() && currentWeekIndex in allWeeks.indices)
        allWeeks[currentWeekIndex] else ""

    Box(modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Summary card
            item {
                SurfaceCard {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                    ) {
                        SourceStatCell(Icons.Default.CalendarMonth, "Total hours", "${calSummary?.total_hours?.let { DateFormat.fmtFloat1(it) } ?: "--"}h", Modifier.weight(1f))
                        SourceStatCell(Icons.AutoMirrored.Filled.EventNote, "Events", "${eventBars.size}", Modifier.weight(1f))
                        SourceStatCell(Icons.Default.CheckCircle, "Proposals", "${proposalBars.size}", Modifier.weight(1f))
                    }
                }
            }

            // Filter chips
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    CategoryFilterChip("Work", AutoLifeSemantic.categoryWork, showWork) { showWork = it }
                    CategoryFilterChip("Health", AutoLifeSemantic.categoryHealth, showHealth) { showHealth = it }
                    CategoryFilterChip("Leisure", AutoLifeSemantic.categoryLeisure, showLeisure) { showLeisure = it }
                }
            }

            // Week navigation
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    IconButton(onClick = { currentWeekIndex-- }, enabled = currentWeekIndex > 0) {
                        Icon(Icons.Default.ChevronLeft, "Previous week")
                    }
                    Text(
                        weekRangeLabel,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    IconButton(onClick = { currentWeekIndex++ }, enabled = currentWeekIndex < allWeeks.size - 1) {
                        Icon(Icons.Default.ChevronRight, "Next week")
                    }
                }
            }

            // Chart (or filtered-empty hint)
            item {
                SurfaceCard {
                    if (weekBars.isEmpty() && weekAllBars.isNotEmpty()) {
                        Column(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                "No events match the current filters",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(8.dp))
                            TextButton(onClick = {
                                showWork = true; showHealth = true; showLeisure = true
                            }) { Text("Clear filters") }
                        }
                    } else {
                        WeekGridChart(bars = weekBars, weekMondayKey = weekMondayKey, onBarClick = { selectedBar = it })
                    }
                }
            }

            // Legend
            item {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(start = 48.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    LegendDot("Work", AutoLifeSemantic.categoryWork)
                    LegendDot("Health", AutoLifeSemantic.categoryHealth)
                    LegendDot("Leisure", AutoLifeSemantic.categoryLeisure)
                    LegendDot("Proposal", proposalColor)
                }
            }

            // AI Proposals
            if (result!!.proposed_changes.isNotEmpty()) {
                val (clearProposals, conflictProposals) = result!!.proposed_changes.partition { change ->
                    val pKey = proposalKey(change)
                    val bar = proposalBars.find { "${it.title}|${it.fullDate}" == pKey }
                    conflictFlags[bar] != true
                }

                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        SectionHeader(
                            title = "Selected proposals",
                        )
                        if (clearProposals.isNotEmpty()) {
                            TextButton(onClick = {
                                clearProposals.forEach { if (!selectedProposals.contains(it)) AnalysisRepository.addProposal(it) }
                            }) {
                                Text("Select All", style = MaterialTheme.typography.labelMedium)
                            }
                        }
                    }
                }

                items(clearProposals) { change ->
                    ProposalRow(
                        change = change,
                        isSelected = selectedProposals.contains(change),
                        hasConflict = false,
                        isExpanded = expandedProposals.contains(proposalKey(change)),
                        onToggleExpand = {
                            val k = proposalKey(change)
                            if (expandedProposals.contains(k)) expandedProposals.remove(k) else expandedProposals.add(k)
                        },
                        onToggleSelect = { checked ->
                            if (checked) AnalysisRepository.addProposal(change) else AnalysisRepository.removeProposal(change)
                        },
                    )
                }

                if (conflictProposals.isNotEmpty()) {
                    item {
                        Text(
                            "Conflicts — review before applying",
                            style = MaterialTheme.typography.labelMedium,
                            color = AutoLifeSemantic.riskMild,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                    items(conflictProposals) { change ->
                        if (selectedProposals.contains(change)) AnalysisRepository.removeProposal(change)
                        ProposalRow(
                            change = change,
                            isSelected = false,
                            hasConflict = true,
                            isExpanded = expandedProposals.contains(proposalKey(change)),
                            onToggleExpand = {
                                val k = proposalKey(change)
                                if (expandedProposals.contains(k)) expandedProposals.remove(k) else expandedProposals.add(k)
                            },
                            onToggleSelect = {},
                        )
                    }
                }

                // Apply button
                item {
                    val isApplying by ProposalApplier.isApplying.collectAsState()
                    Button(
                        onClick = { viewModel.applySelected() },
                        enabled = selectedProposals.isNotEmpty() && !isApplying,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            if (isApplying) "Applying..."
                            else "Apply ${selectedProposals.size} change${if (selectedProposals.size == 1) "" else "s"}",
                        )
                    }
                }
            }
        }

        // Detail bottom sheet
        if (selectedBar != null) {
            EventDetailSheet(bar = selectedBar!!, onDismiss = { selectedBar = null })
        }
    }
}

// ── Chart ────────────────────────────────────────────────────

private val DAYS = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
private const val DAY_START = 6f
private const val DAY_END = 22f
private const val HOUR_SPAN = DAY_END - DAY_START

private fun assignLanes(events: List<CalendarEventBar>): Map<Int, Int> {
    val laneEnds = mutableListOf<Float>()
    val assignment = mutableMapOf<Int, Int>()
    val sorted = events.indices.sortedBy { events[it].startHour }
    for (idx in sorted) {
        val ev = events[idx]
        val lane = laneEnds.indexOfFirst { it <= ev.startHour }
        if (lane >= 0) {
            laneEnds[lane] = ev.startHour + ev.durationHours
            assignment[idx] = lane
        } else {
            assignment[idx] = laneEnds.size
            laneEnds.add(ev.startHour + ev.durationHours)
        }
    }
    return assignment
}

@Composable
private fun WeekGridChart(
    bars: List<CalendarEventBar>,
    weekMondayKey: String,
    onBarClick: (CalendarEventBar) -> Unit,
) {
    val todayKey = remember { currentDateKey() }
    val todayMonday = remember(todayKey) { mondayOfWeek(todayKey) }
    val isCurrentWeek = weekMondayKey == todayMonday
    val todayP = remember(todayKey) { parseISO(todayKey) }
    val todayName = if (todayP != null) DOW_NAMES[dayOfWeekIndex(todayP.year, todayP.month, todayP.day)] else ""
    val dayNumbers = remember(weekMondayKey) {
        if (weekMondayKey.isBlank()) DAYS.associateWith { "" }
        else {
            val p = parseISO(weekMondayKey)
            if (p == null) DAYS.associateWith { "" }
            else {
                var y = p.year; var m = p.month; var d = p.day
                DAYS.associateWith {
                    val label = d.toString()
                    val (ny, nm, nd) = addDays(y, m, d, 1)
                    y = ny; m = nm; d = nd
                    label
                }
            }
        }
    }
    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f)
    val labelColor = MaterialTheme.colorScheme.onSurfaceVariant
    val hitRects = remember(bars) { mutableListOf<BarHitRect>() }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(modifier = Modifier.fillMaxWidth().padding(start = 44.dp)) {
            DAYS.forEach { day ->
                val isToday = isCurrentWeek && day == todayName
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(day, style = MaterialTheme.typography.labelMedium, color = labelColor)
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .background(
                                if (isToday) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else Color.Transparent,
                                RoundedCornerShape(8.dp),
                            ),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            dayNumbers[day] ?: "",
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (isToday) MaterialTheme.colorScheme.primary else labelColor,
                            fontWeight = if (isToday) FontWeight.SemiBold else FontWeight.Normal,
                        )
                    }
                }
            }
        }

        Row(modifier = Modifier.fillMaxWidth().height(520.dp)) {
            Column(
                modifier = Modifier.width(44.dp).fillMaxHeight(),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                listOf("6 AM", "8 AM", "10 AM", "12 PM", "2 PM", "4 PM", "6 PM", "8 PM", "10 PM").forEach {
                    Text(it, style = MaterialTheme.typography.labelSmall, color = labelColor)
                }
            }
            Canvas(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .pointerInput(bars) {
                        detectTapGestures { offset ->
                            val i = hitRects.indexOfFirst { r ->
                                offset.x in r.startX..r.endX && offset.y in r.topY..r.bottomY
                            }
                            if (i in bars.indices) onBarClick(bars[i])
                        }
                    },
            ) {
                hitRects.clear()
                val dayWidth = size.width / DAYS.size
                DAYS.indices.forEach { index ->
                    val x = index * dayWidth
                    drawLine(gridColor, Offset(x, 0f), Offset(x, size.height), 1f)
                }
                drawLine(gridColor, Offset(size.width, 0f), Offset(size.width, size.height), 1f)
                for (h in 6..22 step 2) {
                    val y = ((h - DAY_START) / HOUR_SPAN) * size.height
                    drawLine(gridColor, Offset(0f, y), Offset(size.width, y), 1f)
                }

                bars.forEach { event ->
                    val dayIndex = DAYS.indexOf(event.dayOfWeek).coerceAtLeast(0)
                    val top = ((event.startHour - DAY_START).coerceAtLeast(0f) / HOUR_SPAN) * size.height
                    val height = (event.durationHours.coerceIn(0.1f, HOUR_SPAN) / HOUR_SPAN * size.height).coerceAtLeast(18f)
                    val left = dayIndex * dayWidth + 4.dp.toPx()
                    val width = (dayWidth - 8.dp.toPx()).coerceAtLeast(8f)
                    hitRects.add(BarHitRect(left, left + width, top, top + height))
                    drawRoundRect(
                        color = event.color.copy(alpha = if (event.isProposal) 0.35f else 0.52f),
                        topLeft = Offset(left, top),
                        size = Size(width, height),
                        cornerRadius = CornerRadius(6.dp.toPx(), 6.dp.toPx()),
                    )
                }
            }
        }
    }
}

@Composable
private fun WeekBarChart(
    bars: List<CalendarEventBar>,
    weekMondayKey: String,
    onBarClick: (CalendarEventBar) -> Unit,
) {
    val byDay = bars.groupBy { it.dayOfWeek }
    val todayKey = remember { currentDateKey() }
    val todayMonday = remember(todayKey) { mondayOfWeek(todayKey) }
    val isCurrentWeek = weekMondayKey == todayMonday
    val todayP = remember(todayKey) { parseISO(todayKey) }
    val todayName = if (todayP != null) DOW_NAMES[dayOfWeekIndex(todayP.year, todayP.month, todayP.day)] else ""

    val dayLabels = remember(weekMondayKey) {
        if (weekMondayKey.isBlank()) DAYS.associateWith { it }
        else {
            val p = parseISO(weekMondayKey)
            if (p == null) DAYS.associateWith { it }
            else {
                var y = p.year; var m = p.month; var d = p.day
                DAYS.associateWith { day ->
                    val label = "$day $m/$d"
                    val (ny, nm, nd) = addDays(y, m, d, 1)
                    y = ny; m = nm; d = nd
                    label
                }
            }
        }
    }

    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
    val hourLabelColor = MaterialTheme.colorScheme.onSurfaceVariant

    Column {
        // Hour axis
        Row(
            modifier = Modifier.fillMaxWidth().padding(start = 52.dp, bottom = 2.dp),
        ) {
            val hours = listOf(6, 9, 12, 15, 18, 21, 22)
            hours.zipWithNext().forEach { (h1, h2) ->
                Text(
                    pad2(h1),
                    style = MaterialTheme.typography.labelSmall,
                    color = hourLabelColor,
                    modifier = Modifier.weight((h2 - h1).toFloat()),
                )
            }
        }

        DAYS.forEach { day ->
            val isToday = isCurrentWeek && day == todayName
            DayRow(
                dayDisplayLabel = dayLabels[day] ?: day,
                events = byDay[day] ?: emptyList(),
                isToday = isToday,
                gridColor = gridColor,
                onBarClick = onBarClick,
            )
        }
    }
}

private data class BarHitRect(val startX: Float, val endX: Float, val topY: Float, val bottomY: Float)

@Composable
private fun DayRow(
    dayDisplayLabel: String,
    events: List<CalendarEventBar>,
    isToday: Boolean,
    gridColor: Color,
    onBarClick: (CalendarEventBar) -> Unit,
) {
    val laneAssignment = remember(events) { assignLanes(events) }
    val numLanes = remember(laneAssignment) { (laneAssignment.values.maxOrNull() ?: 0) + 1 }
    val rowHeightDp = (28 * numLanes).dp

    Row(
        modifier = Modifier.fillMaxWidth().height(rowHeightDp).padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            dayDisplayLabel,
            style = MaterialTheme.typography.labelSmall,
            color = if (isToday) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = if (isToday) FontWeight.Bold else FontWeight.Normal,
            modifier = Modifier.width(48.dp),
            maxLines = 1,
        )

        val barHitRects = remember(events) { mutableListOf<BarHitRect>() }

        Canvas(
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight()
                .pointerInput(events) {
                    detectTapGestures { offset ->
                        val i = barHitRects.indexOfFirst { r ->
                            offset.x in r.startX..r.endX && offset.y in r.topY..r.bottomY
                        }
                        if (i in events.indices) onBarClick(events[i])
                    }
                },
        ) {
            barHitRects.clear()

            // Grid lines
            listOf(0f, 3f, 6f, 9f, 12f, 15f).forEach { offset ->
                val x = (offset / HOUR_SPAN) * size.width
                drawLine(gridColor, Offset(x, 0f), Offset(x, size.height), 1f)
            }

            val laneHeight = size.height / numLanes

            events.forEachIndexed { idx, event ->
                val lane = laneAssignment[idx] ?: 0
                val barH = laneHeight * 0.80f
                val barTop = lane * laneHeight + (laneHeight - barH) / 2f
                val startX = ((event.startHour - DAY_START).coerceAtLeast(0f) / HOUR_SPAN * size.width)
                val barW = (event.durationHours.coerceIn(0.05f, HOUR_SPAN) / HOUR_SPAN * size.width).coerceAtLeast(4f)

                barHitRects.add(BarHitRect(startX, startX + barW, barTop, barTop + barH))

                drawRoundRect(
                    color = event.color.copy(alpha = if (event.isProposal) 0.55f else 0.85f),
                    topLeft = Offset(startX, barTop),
                    size = Size(barW, barH),
                    cornerRadius = CornerRadius(4f),
                )
            }
        }
    }
}

// ── Sub-composables ──────────────────────────────────────────

@Composable
private fun CategoryPill(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = MaterialTheme.typography.titleMedium, color = color, fontWeight = FontWeight.SemiBold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun CategoryFilterChip(label: String, chipColor: Color, selected: Boolean, onSelectedChange: (Boolean) -> Unit) {
    FilterChip(
        selected = selected,
        onClick = { onSelectedChange(!selected) },
        label = { Text(label, style = MaterialTheme.typography.labelMedium) },
        leadingIcon = { Box(Modifier.size(8.dp).background(chipColor, CircleShape)) },
    )
}

@Composable
private fun LegendDot(label: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).background(color, RoundedCornerShape(2.dp)))
        Spacer(Modifier.width(4.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ProposalRow(
    change: ProposedChange,
    isSelected: Boolean,
    hasConflict: Boolean,
    isExpanded: Boolean,
    onToggleExpand: () -> Unit,
    onToggleSelect: (Boolean) -> Unit,
) {
    val title = change.title ?: "Untitled"
    val startStr = change.start_time ?: ""
    val desc = change.description
    val accentColor = if (hasConflict) MaterialTheme.colorScheme.error else Color.Transparent

    SurfaceCard(
        modifier = Modifier.drawBehind {
            if (hasConflict) {
                drawRect(
                    color = accentColor,
                    topLeft = Offset(0f, 0f),
                    size = Size(4.dp.toPx(), size.height),
                )
            }
        },
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(
                checked = isSelected,
                enabled = !hasConflict,
                onCheckedChange = onToggleSelect,
            )
            Column(modifier = Modifier.weight(1f).padding(start = 4.dp)) {
                Text(
                    title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = when {
                        hasConflict -> AutoLifeSemantic.riskMild
                        isSelected -> MaterialTheme.colorScheme.primary
                        else -> MaterialTheme.colorScheme.onSurface
                    },
                )
                if (startStr.isNotBlank()) {
                    Text(
                        formatProposalTime(startStr, change.end_time),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (hasConflict) {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 2.dp)) {
                        Icon(Icons.Default.Warning, "Conflict", tint = AutoLifeSemantic.riskMild, modifier = Modifier.size(14.dp))
                        Spacer(Modifier.width(4.dp))
                        Text(
                            "Overlaps existing event",
                            style = MaterialTheme.typography.labelSmall,
                            color = AutoLifeSemantic.riskMild,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
                AnimatedVisibility(visible = isExpanded && !desc.isNullOrBlank(), enter = expandVertically(), exit = shrinkVertically()) {
                    Text(
                        desc ?: "",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }
            if (!desc.isNullOrBlank()) {
                IconButton(onClick = onToggleExpand, modifier = Modifier.size(24.dp)) {
                    Icon(
                        if (isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        if (isExpanded) "Collapse" else "Expand",
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EventDetailSheet(bar: CalendarEventBar, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).background(bar.color, CircleShape))
                Spacer(Modifier.width(8.dp))
                Text(bar.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(12.dp))
            DataRow("Date", bar.dateLabel.ifBlank { bar.dayOfWeek })
            DataRow("Start", "${pad2(bar.startHour.toInt())}:${pad2(((bar.startHour % 1) * 60).toInt())}")
            DataRow("Duration", "${DateFormat.fmtFloat1(bar.durationHours)}h")
            DataRow("Type", when {
                bar.isProposal -> "AI Proposal"
                bar.color == AutoLifeSemantic.categoryWork -> "Work"
                bar.color == AutoLifeSemantic.categoryHealth -> "Health"
                else -> "Leisure"
            })
            Spacer(Modifier.height(24.dp))
        }
    }
}
