package com.google.mediapipe.examples.llminference.ui

import android.content.Intent
import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.google.mediapipe.examples.llminference.AutoLifeService
import com.google.mediapipe.examples.llminference.data.DebugRepository
import com.google.mediapipe.examples.llminference.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RideAppNavHost(
    navController: NavHostController = rememberNavController()
) {
    val context    = LocalContext.current
    val backStack  by navController.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route

    val isServiceRunning by DebugRepository.isServiceRunning.collectAsStateWithLifecycle()

    val topLevelScreens = listOf(
        Screen.Agent,
        Screen.Health,
        Screen.Schedule,
        Screen.Journal,
        Screen.Memory
    )
    val isTopLevel = topLevelScreens.any { it.route == currentRoute }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "> RIDE",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = TerminalGreen
                    )
                },
                navigationIcon = {
                    if (!isTopLevel) {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = "Back",
                                tint = DarkOnSurface
                            )
                        }
                    }
                },
                actions = {
                    // AutoLife service toggle
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(end = 4.dp)
                    ) {
                        // Status dot
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .background(
                                    if (isServiceRunning) TerminalGreen else DarkOnSurfaceDim,
                                    androidx.compose.foundation.shape.CircleShape
                                )
                        )
                        Spacer(modifier = Modifier.width(5.dp))
                        Text(
                            "service",
                            style = MaterialTheme.typography.labelSmall,
                            color = if (isServiceRunning) TerminalGreen else DarkOnSurfaceDim
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Switch(
                            checked = isServiceRunning,
                            onCheckedChange = { shouldStart ->
                                val intent = Intent(context, AutoLifeService::class.java)
                                if (shouldStart) {
                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                        context.startForegroundService(intent)
                                    } else {
                                        context.startService(intent)
                                    }
                                } else {
                                    context.stopService(intent)
                                }
                            },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor   = TerminalGreen,
                                checkedTrackColor   = TerminalGreen.copy(alpha = 0.3f),
                                uncheckedThumbColor = DarkOnSurfaceDim,
                                uncheckedTrackColor = DarkBorder
                            ),
                            modifier = Modifier.height(24.dp)
                        )
                    }
                    // Dev settings (only on top-level screens)
                    if (isTopLevel) {
                        IconButton(onClick = { navController.navigate("dev_dashboard") }) {
                            Text(
                                "⚙",
                                style = MaterialTheme.typography.titleMedium,
                                color = DarkOnSurfaceDim
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor         = DarkSurface,
                    scrolledContainerColor = DarkSurface
                )
            )
        },
        bottomBar = {
            if (isTopLevel) {
                NavigationBar(
                    containerColor = DarkSurface,
                    contentColor   = TerminalGreen,
                    tonalElevation = 0.dp
                ) {
                    topLevelScreens.forEach { screen ->
                        val selected = currentRoute == screen.route
                        NavigationBarItem(
                            selected = selected,
                            onClick  = {
                                navController.navigate(screen.route) {
                                    popUpTo(navController.graph.startDestinationId) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState    = true
                                }
                            },
                            icon = {
                                Icon(
                                    imageVector = screen.icon,
                                    contentDescription = screen.label,
                                    tint = if (selected) TerminalGreen else DarkOnSurfaceDim,
                                    modifier = Modifier.size(18.dp)
                                )
                            },
                            label = {
                                Text(
                                    screen.label,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (selected) TerminalGreen else DarkOnSurfaceDim
                                )
                            },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor   = TerminalGreen,
                                unselectedIconColor = DarkOnSurfaceDim,
                                indicatorColor      = TerminalGreen.copy(alpha = 0.12f)
                            )
                        )
                    }
                }
            }
        },
        containerColor = DarkBackground
    ) { innerPadding ->
        NavHost(
            navController    = navController,
            startDestination = Screen.Agent.route,
            modifier         = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Agent.route)    { AgentScreen() }
            composable(Screen.Health.route)   { HealthScreen() }
            composable(Screen.Schedule.route) { ScheduleScreen() }
            composable(Screen.Journal.route)  { JournalScreen() }
            composable(Screen.Memory.route)   { MemoryScreen() }
            composable("dev_dashboard") {
                DevDashboardScreen(onBackClick = { navController.popBackStack() })
            }
        }
    }
}
