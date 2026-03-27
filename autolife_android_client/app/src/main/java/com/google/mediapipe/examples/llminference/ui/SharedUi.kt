package com.google.mediapipe.examples.llminference.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.mediapipe.examples.llminference.ui.theme.*

// ── Reusable terminal-style UI primitives ─────────────────────

/** Section divider: ── TITLE ──────── */
@Composable
fun SectionHeader(title: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(top = 12.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            "── $title ",
            style = MaterialTheme.typography.labelMedium,
            color = DarkOnSurfaceDim
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .height(1.dp)
                .background(DarkBorder)
        )
    }
}

/** Monospace key: value row */
@Composable
fun MonoRow(
    label: String,
    value: String,
    valueColor: Color = DarkOnSurface,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 1.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            "$label:",
            style = MaterialTheme.typography.labelMedium,
            color = DarkOnSurfaceDim
        )
        Text(
            value,
            style = MaterialTheme.typography.labelMedium,
            color = valueColor
        )
    }
}

/** [STATUS] badge */
@Composable
fun StatusBadge(text: String, color: Color = TerminalGreen) {
    Text(
        "[$text]",
        style = MaterialTheme.typography.labelMedium,
        color = color
    )
}

/** Dark card with a colored left accent stripe */
@Composable
fun TerminalCard(
    modifier: Modifier = Modifier,
    accentColor: Color = TerminalGreen,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(2.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, DarkBorder)
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
                    .padding(12.dp)
                    .fillMaxWidth(),
                content = content
            )
        }
    }
}

/** Map a risk_level string to its display color */
fun riskColor(riskLevel: String): Color = when (riskLevel.lowercase()) {
    "low", "minimal" -> RiskLow
    "mild"           -> RiskMild
    "moderate"       -> RiskModerate
    "moderate-severe",
    "severe"         -> RiskSevere
    else             -> DarkOnSurfaceDim
}
