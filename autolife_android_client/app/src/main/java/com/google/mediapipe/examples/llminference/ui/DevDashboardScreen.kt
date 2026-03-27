package com.google.mediapipe.examples.llminference.ui

import android.graphics.Bitmap
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import android.widget.Toast
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.mediapipe.examples.llminference.JournalGenerator
import com.google.mediapipe.examples.llminference.data.DataExporter
import com.google.mediapipe.examples.llminference.data.DebugRepository
import com.google.mediapipe.examples.llminference.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun DevDashboardScreen(
    onBackClick: () -> Unit  // handled by RideAppNavHost's global back arrow
) {
    val motionStats             by DebugRepository.motionStats.collectAsStateWithLifecycle()
    val locationInfo            by DebugRepository.locationInfo.collectAsStateWithLifecycle()
    val lastJournal             by DebugRepository.lastJournal.collectAsStateWithLifecycle()
    val isDemoMode              by DebugRepository.isDemoMode.collectAsStateWithLifecycle()
    val isPermanentMotionEnabled by DebugRepository.isPermanentMotionEnabled.collectAsStateWithLifecycle()

    val context = LocalContext.current
    val scope   = rememberCoroutineScope()
    var showFullMap    by remember { mutableStateOf(false) }
    var isGenerating   by remember { mutableStateOf(false) }

    if (showFullMap && locationInfo.mapImage != null) {
        FullMapDialog(bitmap = locationInfo.mapImage!!, onDismiss = { showFullMap = false })
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // ── Controls ─────────────────────────────────────────
        SectionHeader("CONTROLS")

        ToggleRow(
            accentColor = TerminalCyan,
            title       = "demo_mode",
            description = "journal interval: 2 min",
            checked     = isDemoMode,
            onChecked   = { DebugRepository.setDemoMode(it) }
        )

        ToggleRow(
            accentColor = TerminalAmber,
            title       = "keep_motion_active",
            description = "sensor update: 2s",
            checked     = isPermanentMotionEnabled,
            onChecked   = { DebugRepository.setPermanentMotionEnabled(it) }
        )

        OutlinedButton(
            onClick = {
                scope.launch {
                    val ok = DataExporter.exportJournals(context)
                    Toast.makeText(
                        context,
                        if (ok) "exported → Downloads/AutoLife" else "export failed",
                        Toast.LENGTH_LONG
                    ).show()
                }
            },
            modifier = Modifier.fillMaxWidth(),
            shape    = RoundedCornerShape(2.dp),
            colors   = ButtonDefaults.outlinedButtonColors(contentColor = TerminalGreen),
            border   = BorderStroke(1.dp, TerminalGreen)
        ) {
            Text("▶  EXPORT ALL JOURNALS", style = MaterialTheme.typography.labelLarge)
        }

        if (isDemoMode) {
            OutlinedButton(
                onClick = {
                    scope.launch {
                        isGenerating = true
                        val ok = JournalGenerator(context).tryGenerateJournal(
                            endTime          = System.currentTimeMillis(),
                            periodDurationMs = 2 * 60_000L
                        )
                        isGenerating = false
                        Toast.makeText(
                            context,
                            if (ok) "journal generated" else "no logs in last 2 min — start service first",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                },
                enabled  = !isGenerating,
                modifier = Modifier.fillMaxWidth(),
                shape    = RoundedCornerShape(2.dp),
                colors   = ButtonDefaults.outlinedButtonColors(contentColor = TerminalCyan),
                border   = BorderStroke(1.dp, if (isGenerating) DarkBorder else TerminalCyan)
            ) {
                Text(
                    if (isGenerating) "█  GENERATING..." else "▶  GENERATE JOURNAL NOW",
                    style = MaterialTheme.typography.labelLarge
                )
            }
            if (isGenerating) {
                LinearProgressIndicator(
                    modifier   = Modifier.fillMaxWidth(),
                    color      = TerminalCyan,
                    trackColor = DarkBorder
                )
            }
        }

        // ── Motion context ────────────────────────────────────
        SectionHeader("MOTION CONTEXT")
        TerminalCard(accentColor = ToolAutoLife) {
            Text(
                "inferred_class: ${motionStats.detectedClass}",
                style = MaterialTheme.typography.labelLarge,
                color = ToolAutoLife,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(6.dp))
            MonoRow("acceleration", "${"%.2f".format(motionStats.acceleration)} m/s²")
            MonoRow("steps_session", "${motionStats.stepCount}")
            MonoRow("speed_gps",    "${"%.2f".format(motionStats.speed)} m/s")
            MonoRow("altitude",     "${"%.1f".format(motionStats.altitude)} m")
        }

        // ── Location context ──────────────────────────────────
        SectionHeader("LOCATION CONTEXT")
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape  = RoundedCornerShape(2.dp),
            colors = CardDefaults.cardColors(containerColor = DarkSurface),
            border = BorderStroke(1.dp, DarkBorder)
        ) {
            Row(modifier = Modifier.height(IntrinsicSize.Min)) {
                Box(
                    modifier = Modifier
                        .width(3.dp)
                        .fillMaxHeight()
                        .background(ToolCalendar)
                )
                Column(modifier = Modifier.padding(12.dp)) {
                    // Map image
                    if (locationInfo.mapImage != null) {
                        val mapBitmap = remember(locationInfo.mapImage) {
                            locationInfo.mapImage!!.asImageBitmap()
                        }
                        Image(
                            bitmap           = mapBitmap,
                            contentDescription = "Satellite Map",
                            modifier         = Modifier
                                .fillMaxWidth()
                                .height(180.dp)
                                .background(Color(0xFF111111), RoundedCornerShape(2.dp))
                                .clickable { showFullMap = true },
                            contentScale     = ContentScale.Crop
                        )
                        Text(
                            "tap to zoom",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    } else {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(80.dp)
                                .background(Color(0xFF111111), RoundedCornerShape(2.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "no_map_captured_yet",
                                style = MaterialTheme.typography.labelMedium,
                                color = DarkOnSurfaceDim
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    // SSIDs
                    MonoRow("ssids_detected", "${locationInfo.ssids.size}")
                    locationInfo.ssids.take(5).forEach { ssid ->
                        Text(
                            "  • $ssid",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim
                        )
                    }
                    if (locationInfo.ssids.size > 5) {
                        Text(
                            "  … +${locationInfo.ssids.size - 5} more",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim
                        )
                    }
                    // Gemini inference
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        "gemini_inference:",
                        style = MaterialTheme.typography.labelMedium,
                        color = DarkOnSurfaceDim
                    )
                    Text(
                        locationInfo.lastInference,
                        style = MaterialTheme.typography.bodyMedium,
                        color = TerminalCyan
                    )
                }
            }
        }

        // ── Latest journal ────────────────────────────────────
        SectionHeader("LATEST JOURNAL ENTRY")
        TerminalCard(accentColor = ToolKEmo) {
            if (lastJournal != null) {
                Text(
                    lastJournal!!,
                    style = MaterialTheme.typography.bodyMedium,
                    color = DarkOnSurface
                )
            } else {
                Text(
                    "no_journal_yet  →  enable demo_mode to accelerate generation",
                    style = MaterialTheme.typography.labelMedium,
                    color = DarkOnSurfaceDim,
                    fontStyle = FontStyle.Italic
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))
    }
}

// ── Toggle row ────────────────────────────────────────────────

@Composable
private fun ToggleRow(
    accentColor: Color,
    title: String,
    description: String,
    checked: Boolean,
    onChecked: (Boolean) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape  = RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, DarkBorder)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment     = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .width(3.dp)
                        .height(32.dp)
                        .background(accentColor)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Column {
                    Text(
                        title,
                        style = MaterialTheme.typography.labelLarge,
                        color = if (checked) accentColor else DarkOnSurface,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        description,
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                }
            }
            Switch(
                checked       = checked,
                onCheckedChange = onChecked,
                colors        = SwitchDefaults.colors(
                    checkedThumbColor   = accentColor,
                    checkedTrackColor   = accentColor.copy(alpha = 0.3f),
                    uncheckedThumbColor = DarkOnSurfaceDim,
                    uncheckedTrackColor = DarkBorder
                )
            )
        }
    }
}

// ── Full-screen map dialog (unchanged layout, dark bg) ────────

@Composable
fun FullMapDialog(bitmap: Bitmap, onDismiss: () -> Unit) {
    Dialog(
        onDismissRequest = onDismiss,
        properties       = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            var scale  by remember { mutableStateOf(1f) }
            var offset by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
            val state  = rememberTransformableState { zoomChange, offsetChange, _ ->
                scale  *= zoomChange
                offset += offsetChange
            }

            Image(
                bitmap             = bitmap.asImageBitmap(),
                contentDescription = "Full Map View",
                modifier           = Modifier
                    .fillMaxSize()
                    .graphicsLayer(
                        scaleX       = scale.coerceIn(1f, 5f),
                        scaleY       = scale.coerceIn(1f, 5f),
                        translationX = offset.x,
                        translationY = offset.y
                    )
                    .transformable(state = state),
                contentScale = ContentScale.Fit
            )

            IconButton(
                onClick  = onDismiss,
                modifier = Modifier
                    .padding(16.dp)
                    .align(Alignment.TopStart)
                    .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(24.dp))
            ) {
                Icon(
                    imageVector        = Icons.Default.Close,
                    contentDescription = "Close",
                    tint               = Color.White
                )
            }

            Text(
                "pinch to zoom  ·  drag to pan",
                color    = Color.White.copy(alpha = 0.5f),
                style    = MaterialTheme.typography.labelSmall,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 24.dp)
            )
        }
    }
}
