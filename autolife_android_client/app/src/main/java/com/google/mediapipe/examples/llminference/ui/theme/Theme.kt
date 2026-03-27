package com.google.mediapipe.examples.llminference.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

// Force dark theme — RIDE is a research/developer tool, always dark.
private val RideColorScheme = darkColorScheme(
    primary          = TerminalGreen,
    onPrimary        = DarkBackground,
    primaryContainer = AgentBlue,
    onPrimaryContainer = DarkOnSurface,
    secondary        = TerminalCyan,
    onSecondary      = DarkBackground,
    tertiary         = TerminalAmber,
    onTertiary       = DarkBackground,
    background       = DarkBackground,
    onBackground     = DarkOnSurface,
    surface          = DarkSurface,
    onSurface        = DarkOnSurface,
    surfaceVariant   = DarkSurfaceVar,
    onSurfaceVariant = DarkOnSurfaceDim,
    outline          = DarkBorder,
    error            = TerminalRed,
    onError          = DarkBackground,
)

@Composable
fun Autolife_projTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = RideColorScheme,
        typography  = RideTypography,
        content     = content
    )
}
