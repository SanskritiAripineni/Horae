package com.google.mediapipe.examples.llminference.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.mediapipe.examples.llminference.data.DebugRepository
import androidx.compose.foundation.clickable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DevDashboardScreen(
    onBackClick: () -> Unit
) {
    val motionStats by DebugRepository.motionStats.collectAsStateWithLifecycle()
    val locationInfo by DebugRepository.locationInfo.collectAsStateWithLifecycle()
    val lastJournal by DebugRepository.lastJournal.collectAsStateWithLifecycle()
    val isDemoMode by DebugRepository.isDemoMode.collectAsStateWithLifecycle()
    
    var showFullMap by remember { mutableStateOf(false) }
    
    if (showFullMap && locationInfo.mapImage != null) {
        FullMapDialog(
            bitmap = locationInfo.mapImage!!,
            onDismiss = { showFullMap = false }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AutoLife Developer Dashboard") },
                navigationIcon = {
                    Button(onClick = onBackClick) { Text("Back") }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Control Panel
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("Demo Mode (2 Mins Interval)", fontWeight = FontWeight.Bold)
                        Text(
                            "Journal Interval: ${if (isDemoMode) "2 mins" else "15 mins"}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Switch(
                        checked = isDemoMode,
                        onCheckedChange = { DebugRepository.setDemoMode(it) }
                    )
                }
            }

            // Motion Context
            Card {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Motion Context (Real-time)", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    DebugRow("Acceleration", "${"%.2f".format(motionStats.acceleration)} m/s²")
                    DebugRow("Steps (Session)", "${motionStats.stepCount}")
                    DebugRow("Speed (GPS)", "${"%.2f".format(motionStats.speed)} m/s")
                    DebugRow("Altitude", "${"%.1f".format(motionStats.altitude)} m")
                    Divider(modifier = Modifier.padding(vertical = 8.dp))
                    Text("Inferred Class: ${motionStats.detectedClass}", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                }
            }

            // Location Context
            Card {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Location Context (15s Interval)", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    if (locationInfo.mapImage != null) {
                        Image(
                            bitmap = locationInfo.mapImage!!.asImageBitmap(),
                            contentDescription = "Satellite Map",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(200.dp)
                                .background(Color.Gray, RoundedCornerShape(8.dp))
                                .clickable { showFullMap = true },
                            contentScale = ContentScale.Crop
                        )
                    } else {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(100.dp)
                                .background(Color.LightGray, RoundedCornerShape(8.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("No Map Image Captured Yet")
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("SSIDs (${locationInfo.ssids.size}):", fontWeight = FontWeight.SemiBold)
                    locationInfo.ssids.take(5).forEach { ssid ->
                        Text("• $ssid", style = MaterialTheme.typography.bodySmall)
                    }
                    if (locationInfo.ssids.size > 5) Text("...and ${locationInfo.ssids.size - 5} more", style = MaterialTheme.typography.bodySmall)
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Gemini Inference:", fontWeight = FontWeight.SemiBold)
                    Text(locationInfo.lastInference, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary)
                }
            }

            // Journal
            Card {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Latest Journal Entry", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    if (lastJournal != null) {
                        Text(lastJournal!!, style = MaterialTheme.typography.bodyMedium)
                    } else {
                        Text("No journal generated yet. Enable Demo Mode to speed up.", style = MaterialTheme.typography.bodySmall, fontStyle = androidx.compose.ui.text.font.FontStyle.Italic)
                    }
                }
            }
        }
    }
}

@Composable
fun FullMapDialog(
    bitmap: Bitmap,
    onDismiss: () -> Unit
) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            // Transformable State for simple pinch-to-zoom
            var scale by remember { mutableStateOf(1f) }
            var offset by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
            val state = rememberTransformableState { zoomChange, offsetChange, _ ->
                scale *= zoomChange
                offset += offsetChange
            }

            Image(
                bitmap = bitmap.asImageBitmap(),
                contentDescription = "Full Map View",
                modifier = Modifier
                    .fillMaxSize()
                    .graphicsLayer(
                        scaleX = scale.coerceIn(1f, 5f),
                        scaleY = scale.coerceIn(1f, 5f),
                        translationX = offset.x,
                        translationY = offset.y
                    )
                    .transformable(state = state),
                contentScale = ContentScale.Fit
            )

            // Close Button
            IconButton(
                onClick = onDismiss,
                modifier = Modifier
                    .padding(16.dp)
                    .align(Alignment.TopStart)
                    .background(Color.Black.copy(alpha = 0.5f), RoundedCornerShape(24.dp))
            ) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Close",
                    tint = Color.White
                )
            }
            
            Text(
                "Pinch to zoom / Drag to move",
                color = Color.White.copy(alpha = 0.7f),
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 24.dp)
            )
        }
    }
}

@Composable
fun DebugRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label)
        Text(value, fontWeight = FontWeight.Bold)
    }
}
