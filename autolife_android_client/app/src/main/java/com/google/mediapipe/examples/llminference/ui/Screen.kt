package com.google.mediapipe.examples.llminference.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val label: String, val icon: ImageVector) {
    object Agent    : Screen("agent",    "AGENT",    Icons.Default.Terminal)
    object Health   : Screen("health",   "HEALTH",   Icons.Default.FavoriteBorder)
    object Schedule : Screen("schedule", "SCHEDULE", Icons.Default.CalendarMonth)
    object Journal  : Screen("journal",  "JOURNAL",  Icons.AutoMirrored.Filled.Article)
    object Memory   : Screen("memory",   "MEMORY",   Icons.Default.Storage)
}
