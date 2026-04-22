package com.autolife.composeapp.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.autolife.shared.model.SignalItem

@Composable
fun SerifHeadline(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = MaterialTheme.colorScheme.onSurface,
) {
    Text(
        text = text,
        modifier = modifier,
        style = MaterialTheme.typography.displayLarge.copy(
            fontFamily = FontFamily.Serif,
            fontWeight = FontWeight.Normal,
        ),
        color = color,
    )
}

@Composable
fun SoftIconCircle(
    icon: ImageVector,
    tint: Color,
    modifier: Modifier = Modifier,
    size: Dp = 52.dp,
    iconSize: Dp = 28.dp,
) {
    Surface(
        modifier = modifier.size(size),
        shape = CircleShape,
        color = tint.copy(alpha = 0.11f),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(iconSize))
        }
    }
}

@Composable
fun EvidenceChip(
    label: String,
    kind: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
) {
    val color = signalToneColor(kind)
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.55f)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(18.dp), tint = color)
            Text(
                label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
fun SignalPanel(
    title: String,
    items: List<SignalItem>,
    tone: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
) {
    val color = signalToneColor(tone)
    SurfaceCard(modifier = modifier) {
        Text(title, style = MaterialTheme.typography.titleMedium, color = color)
        Spacer(Modifier.height(12.dp))
        if (items.isEmpty()) {
            Text("No signals detected", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            items.forEach { item ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
                    verticalAlignment = Alignment.Top,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Icon(icon, contentDescription = null, modifier = Modifier.size(18.dp), tint = color)
                    Column(Modifier.weight(1f)) {
                        Text(item.label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
                        if (!item.detail.isNullOrBlank()) {
                            Text(item.detail!!, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SourceStatCell(
    icon: ImageVector,
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(28.dp))
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
        Text(value, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun CategoryBadge(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        color = color.copy(alpha = 0.12f),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            color = color,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
        )
    }
}

@Composable
fun PracticeRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    tags: List<Pair<String, Color>>,
    accent: Color,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
) {
    SurfaceCard(
        modifier = modifier.then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SoftIconCircle(icon = icon, tint = accent, size = 56.dp, iconSize = 30.dp)
            Column(Modifier.weight(1f)) {
                Text(
                    title,
                    style = MaterialTheme.typography.headlineMedium.copy(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Normal),
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (subtitle.isNotBlank()) {
                    Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (tags.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        tags.take(3).forEach { (tag, color) ->
                            CategoryBadge(text = tag, color = color)
                        }
                    }
                }
            }
            Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun signalToneColor(kind: String): Color {
    return when (kind.lowercase()) {
        "concern", "warning", "high" -> MaterialTheme.colorScheme.error
        "protective", "productive", "positive" -> MaterialTheme.colorScheme.secondary
        "sleep" -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.primary
    }
}

@Composable
fun MutedDivider(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(1.dp).background(MaterialTheme.colorScheme.outline.copy(alpha = 0.45f)))
}
