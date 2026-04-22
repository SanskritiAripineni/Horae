package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Battery5Bar
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.foundation.Image
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.autolife.composeapp.platform.ActiveBatteryAssessment
import com.autolife.composeapp.platform.BatteryAppStateIntent
import com.autolife.composeapp.platform.BatteryAssessmentPair
import com.autolife.composeapp.platform.BatteryAssessmentRecord
import com.autolife.composeapp.platform.BatteryScreenIntent
import com.autolife.composeapp.platform.BatteryTestProfile
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.platform.rememberLocationPreviewImage
import com.autolife.composeapp.ui.components.DataRow
import com.autolife.composeapp.ui.components.IconBulletItem
import com.autolife.composeapp.ui.components.SectionHeader
import com.autolife.composeapp.ui.components.StatusPill
import com.autolife.composeapp.ui.components.SurfaceCard
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.platform.currentTimeMillis
import kotlinx.coroutines.delay
import kotlin.math.pow
import kotlin.math.roundToLong

private fun Double.fmt(decimals: Int): String {
    val factor = 10.0.pow(decimals)
    val rounded = (this * factor).roundToLong() / factor
    val str = rounded.toString()
    val dot = str.indexOf('.')
    if (dot == -1) return str + "." + "0".repeat(decimals)
    val currentDecimals = str.length - dot - 1
    return if (currentDecimals >= decimals) str.substring(0, dot + decimals + 1)
    else str + "0".repeat(decimals - currentDecimals)
}

@Composable
fun DevDashboardScreen() {
    val motionState by PlatformStateProvider.motionState.collectAsState()
    val serviceState by PlatformStateProvider.serviceState.collectAsState()
    val locationState by PlatformStateProvider.locationState.collectAsState()
    val lastJournal by PlatformStateProvider.lastJournal.collectAsState()
    val isPermanentMotion by PlatformStateProvider.isPermanentMotionEnabled.collectAsState()
    val batteryState by PlatformStateProvider.batteryState.collectAsState()
    val locationPreview = rememberLocationPreviewImage(locationState.mapPreviewBytes)

    var isGenerating by remember { mutableStateOf(false) }
    var batteryNotes by remember { mutableStateOf("") }
    var selectedProfile by remember { mutableStateOf(BatteryTestProfile.IDLE_BASELINE) }
    var selectedDurationMinutes by remember { mutableStateOf(30) }
    var selectedScreenIntent by remember { mutableStateOf(BatteryScreenIntent.MOSTLY_SCREEN_OFF) }
    var selectedAppStateIntent by remember { mutableStateOf(BatteryAppStateIntent.MOSTLY_BACKGROUND) }
    val activeAssessment = batteryState.activeAssessment
    val nowMs by produceState(initialValue = currentTimeMillis(), activeAssessment?.autoStopAtMs) {
        while (true) {
            value = currentTimeMillis()
            delay(1_000L)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SurfaceCard {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Service Status", style = MaterialTheme.typography.titleMedium)
                StatusPill(
                    text = if (serviceState.isRunning) "Running" else "Stopped",
                    color = if (serviceState.isRunning) AutoLifeSemantic.riskLow
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        SectionHeader("Controls")
        SurfaceCard {
            ToggleRow(
                title = "Demo Mode",
                description = "Journal interval: 2 min",
                checked = serviceState.isDemoMode,
                onCheckedChange = { PlatformStateProvider.toggleDemoMode(it) },
            )

            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

            ToggleRow(
                title = "Keep Motion Active",
                description = "Sensor update: 2s",
                checked = isPermanentMotion,
                onCheckedChange = { PlatformStateProvider.togglePermanentMotion(it) },
            )

            if (PlatformStateProvider.onExportRequested != null) {
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = { PlatformStateProvider.onExportRequested?.invoke() },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.Download, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Export All Journals")
                }
            }

            if (serviceState.isDemoMode && PlatformStateProvider.onGenerateJournalRequested != null) {
                Spacer(Modifier.height(4.dp))
                OutlinedButton(
                    onClick = {
                        isGenerating = true
                        PlatformStateProvider.onGenerateJournalRequested?.invoke()
                        isGenerating = false
                    },
                    enabled = !isGenerating,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (isGenerating) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.PlayArrow, null, Modifier.size(18.dp))
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(if (isGenerating) "Generating..." else "Generate Journal Now")
                }
            }
        }

        SectionHeader("Battery Assessment")
        SurfaceCard {
            val currentBattery = batteryState.currentBatteryPercent

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Current Battery", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                    Text(
                        if (currentBattery != null) "$currentBattery%" else "Unknown",
                        style = MaterialTheme.typography.headlineSmall,
                        color = if ((currentBattery ?: 100) <= 20) AutoLifeSemantic.riskSevere else MaterialTheme.colorScheme.primary,
                    )
                }
                OutlinedButton(onClick = { PlatformStateProvider.refreshBatteryLevel() }) {
                    Icon(Icons.Default.Refresh, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Refresh")
                }
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Profile",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                BatteryTestProfile.entries.forEach { profile ->
                    FilterChip(
                        selected = selectedProfile == profile,
                        onClick = { selectedProfile = profile },
                        label = { Text(profile.displayName()) },
                    )
                }
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Duration",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(30, 60).forEach { minutes ->
                    FilterChip(
                        selected = selectedDurationMinutes == minutes,
                        onClick = { selectedDurationMinutes = minutes },
                        label = { Text("${minutes}m") },
                    )
                }
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Screen Intent",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(8.dp))
            EnumSelectorRow(
                values = BatteryScreenIntent.entries,
                selected = selectedScreenIntent,
                label = { it.displayName() },
                onSelected = { selectedScreenIntent = it },
            )

            Spacer(Modifier.height(12.dp))
            Text(
                "App State Intent",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(8.dp))
            EnumSelectorRow(
                values = BatteryAppStateIntent.entries,
                selected = selectedAppStateIntent,
                label = { it.displayName() },
                onSelected = { selectedAppStateIntent = it },
            )

            Spacer(Modifier.height(12.dp))
            Text(
                selectedProfile.instruction(),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            val previewMessages = remember(
                selectedProfile,
                batteryState.completedAssessments,
                batteryState.currentBatteryPercent,
                serviceState.isDemoMode,
            ) {
                PlatformStateProvider.previewBatterySetupMessages(selectedProfile)
            }
            val setupMessages = if (activeAssessment == null) previewMessages else batteryState.setupMessages
            if (setupMessages.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                setupMessages.forEach { message ->
                    StatusLine(message)
                }
            }

            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = batteryNotes,
                onValueChange = { batteryNotes = it },
                label = { Text("Optional notes") },
                placeholder = { Text("e.g. office Wi-Fi, no charging, airplane mode off") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )

            Spacer(Modifier.height(12.dp))
            Button(
                onClick = {
                    PlatformStateProvider.startBatteryAssessment(
                        profile = selectedProfile,
                        screenIntent = selectedScreenIntent,
                        appStateIntent = selectedAppStateIntent,
                        notes = batteryNotes,
                        targetDurationMinutes = selectedDurationMinutes,
                    )
                },
                enabled = activeAssessment == null && currentBattery != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Start Assessment")
            }

            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = {
                        PlatformStateProvider.completeBatteryAssessment(batteryNotes)
                        batteryNotes = ""
                    },
                    enabled = activeAssessment != null && currentBattery != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Default.Stop, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Stop Run")
                }
                OutlinedButton(
                    onClick = { PlatformStateProvider.exportBatteryAssessmentReport() },
                    enabled = batteryState.completedAssessments.isNotEmpty(),
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Default.Download, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Export Report")
                }
            }

            if (activeAssessment != null) {
                Spacer(Modifier.height(12.dp))
                ActiveAssessmentCard(activeAssessment = activeAssessment, nowMs = nowMs)
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Interpretation",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Text(
                batteryState.summary.interpretation,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (batteryState.summary.latestPairs.isNotEmpty()) {
            SurfaceCard {
                Text(
                    "Recent Paired Summaries",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.height(8.dp))
                batteryState.summary.latestPairs.forEach { pair ->
                    PairSummary(pair)
                    Spacer(Modifier.height(10.dp))
                }
            }
        }

        if (batteryState.completedAssessments.isNotEmpty()) {
            SurfaceCard {
                Text(
                    "Historical Battery Runs",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.height(8.dp))
                batteryState.completedAssessments.takeLast(6).reversed().forEach { record ->
                    IconBulletItem(
                        icon = Icons.Default.Battery5Bar,
                        iconTint = when (record.profile) {
                            BatteryTestProfile.IDLE_BASELINE -> AutoLifeSemantic.categoryHealth
                            BatteryTestProfile.TYPICAL_BACKGROUND_USE -> AutoLifeSemantic.toolAutoLife
                        },
                        text = "${record.platform} ${record.profile.displayName()}: " +
                            "${record.startBatteryPercent}% -> ${record.endBatteryPercent}% " +
                            "over ${record.durationMinutes.fmt(1)} min " +
                            "(${record.drainPerHourPercent.fmt(1)}%/hr)",
                    )
                    if (record.warningFlags.isNotEmpty()) {
                        Text(
                            record.warningFlags.joinToString(" | ") { it.displayText() },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(start = 28.dp, top = 2.dp),
                        )
                    }
                }
            }
        }

        SectionHeader("Motion Context")
        SurfaceCard {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Detected Activity",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                StatusPill(text = motionState.detectedClass, color = AutoLifeSemantic.toolAutoLife)
            }
            Spacer(Modifier.height(8.dp))
            DataRow("Acceleration", "${motionState.acceleration.fmt(2)} m/s\u00B2")
            DataRow("Steps (session)", "${motionState.stepCount}")
            DataRow("GPS Speed", "${motionState.speed.fmt(2)} m/s")
            DataRow("Altitude", "${motionState.altitude.fmt(1)} m")
        }

        SectionHeader("Location Context")
        SurfaceCard {
            if (locationPreview != null) {
                Text(
                    "Map Snapshot Used For Inference",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.height(8.dp))
                Image(
                    bitmap = locationPreview,
                    contentDescription = "Processed map preview centered on current location",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(168.dp)
                        .clip(RoundedCornerShape(16.dp)),
                    contentScale = ContentScale.Crop,
                )
                Spacer(Modifier.height(12.dp))
            }

            DataRow("Latitude", locationState.latitude.fmt(6))
            DataRow("Longitude", locationState.longitude.fmt(6))

            Spacer(Modifier.height(8.dp))
            Text(
                "WiFi Networks (${locationState.ssids.size})",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            if (locationState.ssids.isEmpty()) {
                Text(
                    "No networks detected",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                locationState.ssids.take(5).forEach { ssid ->
                    Text(
                        "  \u2022 $ssid",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (locationState.ssids.size > 5) {
                    Text(
                        "  \u2026 +${locationState.ssids.size - 5} more",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(8.dp))
            Text(
                "Gemini Inference",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Text(
                locationState.lastInference,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }

        SectionHeader("Latest Journal Entry")
        SurfaceCard {
            val journal = lastJournal
            if (journal != null) {
                Text(journal, style = MaterialTheme.typography.bodyMedium)
            } else {
                Text(
                    "No journal generated yet. Enable demo mode and start the service to accelerate generation.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        Spacer(Modifier.height(16.dp))
    }
}

private fun formatRemainingTime(remainingMs: Long): String {
    val totalSeconds = remainingMs / 1_000L
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "${minutes}:${seconds.toString().padStart(2, '0')} remaining"
}

@Composable
private fun ToggleRow(
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
            Text(
                description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun <T> EnumSelectorRow(
    values: List<T>,
    selected: T,
    label: (T) -> String,
    onSelected: (T) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        values.forEach { value ->
            FilterChip(
                selected = selected == value,
                onClick = { onSelected(value) },
                label = { Text(label(value)) },
            )
        }
    }
}

@Composable
private fun StatusLine(text: String) {
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer,
        tonalElevation = 0.dp,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSecondaryContainer,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
        )
    }
}

@Composable
private fun ActiveAssessmentCard(
    activeAssessment: ActiveBatteryAssessment,
    nowMs: Long,
) {
    SurfaceCard {
        StatusPill(
            text = "Running ${activeAssessment.profile.displayName()}",
            color = AutoLifeSemantic.toolVectorDB,
        )
        Spacer(Modifier.height(8.dp))
        DataRow("Start battery", "${activeAssessment.startBatteryPercent}%")
        DataRow("Target duration", "${activeAssessment.targetDurationMinutes} min")
        DataRow(
            "Time remaining",
            formatRemainingTime((activeAssessment.autoStopAtMs - nowMs).coerceAtLeast(0L)),
        )
        DataRow("Profile applied", if (activeAssessment.autoConfigurationApplied) "Yes" else "Needs review")
        DataRow("Network", activeAssessment.environment.networkSummary)
        DataRow("Screen intent", activeAssessment.environment.screenIntent.displayName())
        DataRow("App state intent", activeAssessment.environment.appStateIntent.displayName())
        Spacer(Modifier.height(8.dp))
        StatusLine("Checklist: battery captured, profile applied, timer running.")
        Spacer(Modifier.height(6.dp))
        Text(
            activeAssessment.profile.instruction(),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PairSummary(pair: BatteryAssessmentPair) {
    Text(
        pair.platform,
        style = MaterialTheme.typography.bodyLarge,
        fontWeight = FontWeight.Medium,
    )
    Spacer(Modifier.height(4.dp))
    Text(
        "Baseline ${pair.baseline.drainPerHourPercent.fmt(1)}%/hr, typical use ${pair.typicalUse.drainPerHourPercent.fmt(1)}%/hr, delta ${pair.deltaPerHourPercent.fmt(1)}%/hr.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Text(
        pair.confidenceLabel,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}
