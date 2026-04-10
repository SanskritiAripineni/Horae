package com.autolife.composeapp.platform

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import com.autolife.composeapp.ui.screens.DevDashboardScreen
import androidx.compose.runtime.Composable
import androidx.compose.foundation.layout.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
actual fun ServiceToggle(isRunning: Boolean, onToggle: (Boolean) -> Unit) {
    // The actual service start/stop intent is handled by the androidApp module.
    // This just renders the switch — the androidApp host wires the intent logic
    // by passing the onToggle callback that calls startForegroundService/stopService.
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(end = 4.dp)
    ) {
        Text(
            text = if (isRunning) "Active" else "Off",
            style = MaterialTheme.typography.labelMedium,
            color = if (isRunning) MaterialTheme.colorScheme.secondary
                    else MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(6.dp))
        Switch(
            checked = isRunning,
            onCheckedChange = onToggle,
            modifier = Modifier.height(24.dp),
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
