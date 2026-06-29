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
    primaryContainer = AutoLifeLight.primaryContainer,
    onPrimaryContainer = AutoLifeLight.onPrimaryContainer,
    onPrimary = AutoLifeLight.onPrimary,
    secondary = AutoLifeLight.secondary,
    secondaryContainer = AutoLifeLight.secondaryContainer,
    onSecondaryContainer = AutoLifeLight.onSecondaryContainer,
    tertiary = AutoLifeLight.tertiary,
    tertiaryContainer = AutoLifeLight.tertiaryContainer,
    onTertiaryContainer = AutoLifeLight.onTertiaryContainer,
    error = AutoLifeLight.error,
    errorContainer = AutoLifeLight.errorContainer,
    onErrorContainer = AutoLifeLight.onErrorContainer,
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
    primaryContainer = AutoLifeDark.primaryContainer,
    onPrimaryContainer = AutoLifeDark.onPrimaryContainer,
    onPrimary = AutoLifeDark.onPrimary,
    secondary = AutoLifeDark.secondary,
    secondaryContainer = AutoLifeDark.secondaryContainer,
    onSecondaryContainer = AutoLifeDark.onSecondaryContainer,
    tertiary = AutoLifeDark.tertiary,
    tertiaryContainer = AutoLifeDark.tertiaryContainer,
    onTertiaryContainer = AutoLifeDark.onTertiaryContainer,
    error = AutoLifeDark.error,
    errorContainer = AutoLifeDark.errorContainer,
    onErrorContainer = AutoLifeDark.onErrorContainer,
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
