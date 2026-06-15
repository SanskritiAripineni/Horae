package com.autolife.composeapp.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.autolife.shared.model.ProposedChange

@Composable
fun CalendarWriteConfirmationDialog(
    changes: List<ProposedChange>,
    calendarName: String = "Google Calendar",
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    if (changes.isEmpty()) return

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Confirm Calendar Write") },
        text = {
            Column {
                Text(
                    "You are about to apply ${changes.size} change${if (changes.size == 1) "" else "s"} to $calendarName.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(12.dp))
                changes.take(5).forEach { change ->
                    Text(
                        text = "• ${calendarChangeLabel(change)}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                if (changes.size > 5) {
                    Text(
                        text = "• ${changes.size - 5} more",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Spacer(Modifier.height(12.dp))
                Text(
                    "This will create, update, or delete calendar entries.",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text("Confirm & Apply")
            }
        },
    )
}

private fun calendarChangeLabel(change: ProposedChange): String {
    val title = change.title?.takeIf { it.isNotBlank() } ?: "Untitled"
    val time = change.start_time
        ?.replace("T", " ")
        ?.take(16)
        ?.takeIf { it.isNotBlank() }
    val action = change.action
        ?.lowercase()
        ?.takeIf { it.isNotBlank() }
        ?: if (change.event_id.isNullOrBlank()) "create" else "update"

    return listOfNotNull(title, time, "($action)").joinToString(" ")
}
