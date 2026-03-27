package com.google.mediapipe.examples.llminference.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.mediapipe.examples.llminference.data.SensorLog
import com.google.mediapipe.examples.llminference.ui.theme.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ── Shared sensor-log composables used by JournalScreen ───────

@Composable
fun LogsList(logs: List<SensorLog>) {
    if (logs.isEmpty()) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(DarkBackground),
            contentAlignment = androidx.compose.ui.Alignment.Center
        ) {
            Text(
                "No logs yet. Start the AutoLife service.",
                style = MaterialTheme.typography.labelMedium,
                color = DarkOnSurfaceDim
            )
        }
        return
    }
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground),
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        items(logs, key = { it.id }) { log -> LogCard(log) }
    }
}

@Composable
fun LogCard(log: SensorLog) {
    val accentColor = when (log.type) {
        "MOTION"   -> ToolAutoLife
        "LOCATION" -> ToolCalendar
        "WIFI"     -> ToolVectorDB
        else       -> DarkOnSurfaceDim
    }
    Card(
        shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = androidx.compose.foundation.BorderStroke(1.dp, DarkBorder)
    ) {
        Row(modifier = Modifier.height(IntrinsicSize.Min)) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .fillMaxHeight()
                    .background(accentColor)
            )
            Column(
                modifier = Modifier
                    .padding(10.dp)
                    .fillMaxWidth()
            ) {
                Row(
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        log.type,
                        style = MaterialTheme.typography.labelMedium,
                        color = accentColor,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        formatTime(log.timestamp),
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                }
                Spacer(modifier = Modifier.height(3.dp))
                Text(
                    log.content,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 6,
                    color = DarkOnSurface
                )
            }
        }
    }
}

fun formatTime(timestamp: Long): String {
    val sdf = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
    return sdf.format(Date(timestamp))
}
