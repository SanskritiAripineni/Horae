package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Battery5Bar
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.autolife.composeapp.platform.BatteryTestCondition
import com.autolife.composeapp.platform.PlatformStateProvider
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

    var isGenerating by remember { mutableStateOf(false) }
    var batteryNotes by remember { mutableStateOf("") }
    var autoDurationMinutes by remember { mutableStateOf(30) }
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
        // ── Service status ──────────────────────────────────────
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

        // ── Controls ────────────────────────────────────────────
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
                "Auto duration",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(1, 5, 30).forEach { minutes ->
                    FilterChip(
                        selected = autoDurationMinutes == minutes,
                        onClick = { autoDurationMinutes = minutes },
                        label = { Text("${minutes}m") },
                    )
                }
            }

            Spacer(Modifier.height(12.dp))
            Text(
                "Use one baseline run with collection off and one active run with normal collection on. Thirty minutes per run is enough for the IRB battery statement.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = batteryNotes,
                onValueChange = { batteryNotes = it },
                label = { Text("Run notes") },
                placeholder = { Text("e.g. screen off, Wi-Fi on, service enabled") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )

            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = { PlatformStateProvider.startBatteryAssessment(BatteryTestCondition.BASELINE, batteryNotes) },
                    enabled = activeAssessment == null && currentBattery != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Start Baseline")
                }
                Button(
                    onClick = { PlatformStateProvider.startBatteryAssessment(BatteryTestCondition.ACTIVE, batteryNotes) },
                    enabled = activeAssessment == null && currentBattery != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Start Active")
                }
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

            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = {
                        PlatformStateProvider.startBatteryAssessment(
                            condition = BatteryTestCondition.BASELINE,
                            notes = batteryNotes,
                            autoDurationMinutes = autoDurationMinutes,
                        )
                    },
                    enabled = activeAssessment == null && currentBattery != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Auto Baseline")
                }
                OutlinedButton(
                    onClick = {
                        PlatformStateProvider.startBatteryAssessment(
                            condition = BatteryTestCondition.ACTIVE,
                            notes = batteryNotes,
                            autoDurationMinutes = autoDurationMinutes,
                        )
                    },
                    enabled = activeAssessment == null && currentBattery != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Auto Active")
                }
            }

            if (activeAssessment != null) {
                Spacer(Modifier.height(12.dp))
                StatusPill(
                    text = "Running ${activeAssessment.condition.name.lowercase()} test",
                    color = AutoLifeSemantic.toolVectorDB,
                )
                Spacer(Modifier.height(8.dp))
                DataRow("Started battery", "${activeAssessment.startBatteryPercent}%")
                DataRow("Service", if (activeAssessment.serviceEnabledAtStart) "On" else "Off")
                DataRow("Demo mode", if (activeAssessment.demoModeAtStart) "On" else "Off")
                DataRow("Permanent motion", if (activeAssessment.permanentMotionAtStart) "On" else "Off")
                if (activeAssessment.autoStopAtMs != null) {
                    DataRow(
                        "Auto stop",
                        formatRemainingTime((activeAssessment.autoStopAtMs - nowMs).coerceAtLeast(0L)),
                    )
                }
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

        if (batteryState.completedAssessments.isNotEmpty()) {
            SurfaceCard {
                Text(
                    "Recent Battery Runs",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.height(8.dp))
                batteryState.completedAssessments.takeLast(4).reversed().forEach { record ->
                    IconBulletItem(
                        icon = Icons.Default.Battery5Bar,
                        iconTint = when (record.condition) {
                            BatteryTestCondition.BASELINE -> AutoLifeSemantic.categoryHealth
                            BatteryTestCondition.ACTIVE -> AutoLifeSemantic.toolAutoLife
                        },
                        text = "${record.platform} ${record.condition.name.lowercase()}: " +
                            "${record.startBatteryPercent}% -> ${record.endBatteryPercent}% " +
                            "over ${record.durationMinutes.fmt(1)} min " +
                            "(${record.drainPerHourPercent.fmt(1)}%/hr)",
                    )
                }
            }
        }

        // ── Motion context ──────────────────────────────────────
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

        // ── Location context ────────────────────────────────────
        SectionHeader("Location Context")
        SurfaceCard {
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

        // ── Latest journal ──────────────────────────────────────
        SectionHeader("Latest Journal Entry")
        SurfaceCard {
            if (lastJournal != null) {
                Text(lastJournal!!, style = MaterialTheme.typography.bodyMedium)
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
