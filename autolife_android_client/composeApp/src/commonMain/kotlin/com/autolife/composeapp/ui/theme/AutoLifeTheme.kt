package com.autolife.composeapp.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    background = AutoLifeLight.background,
    surface = AutoLifeLight.surface,
    surfaceVariant = AutoLifeLight.surfaceSecondary,
    onBackground = AutoLifeLight.onBackground,
    onSurface = AutoLifeLight.onSurface,
    onSurfaceVariant = AutoLifeLight.onSurfaceDim,
    outline = AutoLifeLight.outline,
    primary = AutoLifeLight.primary,
    onPrimary = AutoLifeLight.onPrimary,
    secondary = AutoLifeLight.secondary,
    tertiary = AutoLifeLight.tertiary,
    error = AutoLifeLight.error,
)

private val DarkColorScheme = darkColorScheme(
    background = AutoLifeDark.background,
    surface = AutoLifeDark.surface,
    surfaceVariant = AutoLifeDark.surfaceSecondary,
    onBackground = AutoLifeDark.onBackground,
    onSurface = AutoLifeDark.onSurface,
    onSurfaceVariant = AutoLifeDark.onSurfaceDim,
    outline = AutoLifeDark.outline,
    primary = AutoLifeDark.primary,
    onPrimary = AutoLifeDark.onPrimary,
    secondary = AutoLifeDark.secondary,
    tertiary = AutoLifeDark.tertiary,
    error = AutoLifeDark.error,
)

@Composable
fun AutoLifeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        typography = AutoLifeTypography,
        content = content
    )
}
