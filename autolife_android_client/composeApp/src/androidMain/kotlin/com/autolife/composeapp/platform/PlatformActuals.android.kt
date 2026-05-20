package com.autolife.composeapp.platform

import android.graphics.BitmapFactory
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import com.autolife.composeapp.ui.screens.DevDashboardScreen
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.foundation.layout.*
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.autolife.shared.model.RawDayMarkers
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
actual fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(end = 4.dp)
    ) {
        Text(
            text = if (isRunning) "Collecting" else "Paused",
            style = MaterialTheme.typography.labelMedium,
            color = if (isRunning) MaterialTheme.colorScheme.secondary
                    else MaterialTheme.colorScheme.error,
        )
        Spacer(Modifier.width(6.dp))
        Switch(
            checked = isRunning,
            onCheckedChange = onToggle,
            colors = SwitchDefaults.colors(
                checkedThumbColor = MaterialTheme.colorScheme.onPrimary,
                checkedTrackColor = MaterialTheme.colorScheme.secondary,
                uncheckedThumbColor = MaterialTheme.colorScheme.error,
                uncheckedTrackColor = MaterialTheme.colorScheme.error.copy(alpha = 0.16f),
                uncheckedBorderColor = MaterialTheme.colorScheme.error.copy(alpha = 0.36f),
            ),
            modifier = Modifier
                .height(24.dp)
                .semantics {
                    contentDescription = "AutoLife background collection"
                    stateDescription = if (isRunning) "Collecting" else "Paused"
                    role = Role.Switch
                },
        )
    }
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
    withContext(Dispatchers.IO) {
        BehavioralMarkerAggregator.aggregate(nDays)
    }

actual fun openNativeCalendar() {
    val ctx = AppContextHolder.context ?: return
    val intent = android.content.Intent(android.content.Intent.ACTION_VIEW).apply {
        data = android.provider.CalendarContract.CONTENT_URI
        flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK
    }
    runCatching { ctx.startActivity(intent) }
}
