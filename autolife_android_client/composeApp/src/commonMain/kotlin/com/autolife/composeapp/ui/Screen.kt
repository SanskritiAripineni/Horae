package com.autolife.composeapp.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Storage
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val label: String, val icon: ImageVector) {
    data object Agent    : Screen("agent",    "Agent",    Icons.Default.Home)
    data object Health   : Screen("health",   "Health",   Icons.Default.FavoriteBorder)
    data object Schedule : Screen("schedule", "Schedule", Icons.Default.CalendarMonth)
    data object Journal  : Screen("journal",  "Journal",  Icons.AutoMirrored.Filled.Article)
    data object Memory   : Screen("memory",   "Memory",   Icons.Default.Storage)
}
