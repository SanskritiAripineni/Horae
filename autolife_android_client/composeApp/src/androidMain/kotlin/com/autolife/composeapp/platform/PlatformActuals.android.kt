package com.autolife.composeapp.platform

import android.graphics.BitmapFactory
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Text
import com.autolife.composeapp.ui.screens.DevDashboardScreen
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.autolife.shared.model.RawDayMarkers

@Composable
actual fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit) {
    val color = if (isRunning) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant
    AssistChip(
        onClick = { onToggle(!isRunning) },
        label = {
            Text(
                text = if (isRunning) "Collecting" else "Paused",
                style = MaterialTheme.typography.labelLarge,
            )
        },
        leadingIcon = {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(color, CircleShape),
            )
        },
        colors = AssistChipDefaults.assistChipColors(
            containerColor = color.copy(alpha = 0.09f),
            labelColor = color,
            leadingIconContentColor = color,
        ),
        border = BorderStroke(1.dp, color.copy(alpha = 0.22f)),
        modifier = Modifier
            .heightIn(min = 40.dp)
            .padding(end = 2.dp),
    )
}

@Composable
actual fun DevDashboardRoute(onBackClick: () -> Unit) {
    DevDashboardScreen()
}

actual fun currentDateKey(): String {
    val cal = java.util.Calendar.getInstance()
    return "%04d-%02d-%02d".format(
        cal.get(java.util.Calendar.YEAR),
        cal.get(java.util.Calendar.MONTH) + 1,
        cal.get(java.util.Calendar.DAY_OF_MONTH),
    )
}

@Composable
actual fun rememberLocationPreviewImage(imageBytes: ByteArray?): ImageBitmap? {
    return remember(imageBytes) {
        if (imageBytes == null) {
            null
        } else {
            BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)?.asImageBitmap()
        }
    }
}

actual suspend fun getBehavioralMarkers(nDays: Int): List<RawDayMarkers> =
    BehavioralMarkerAggregator.aggregate(nDays)
