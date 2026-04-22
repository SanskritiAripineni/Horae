package com.autolife.composeapp.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.autolife.composeapp.platform.DevDashboardRoute
import com.autolife.composeapp.platform.PlatformStateProvider
import com.autolife.composeapp.platform.ServiceToggle
import com.autolife.composeapp.ui.screens.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutoLifeNavHost(
    navController: NavHostController = rememberNavController(),
    onServiceToggle: (Boolean) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val backStack by navController.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    val serviceState by PlatformStateProvider.serviceState.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(Unit) {
        SnackbarBus.messages.collect { msg ->
            snackbarHostState.showSnackbar(msg)
        }
    }

    val topLevelScreens = listOf(
        Screen.Agent, Screen.Health, Screen.Schedule, Screen.Journal, Screen.Memory,
    )
    val isTopLevel = topLevelScreens.any { it.route == currentRoute }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = {
                    Text("AutoLife", style = MaterialTheme.typography.titleLarge)
                },
                navigationIcon = {
                    if (!isTopLevel) {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                        }
                    }
                },
                actions = {
                    Box(modifier = Modifier.testTag("service_toggle")) {
                        ServiceToggle(
                            isRunning = serviceState.isRunning,
                            onToggle = onServiceToggle,
                        )
                    }
                    if (isTopLevel) {
                        IconButton(onClick = { navController.navigate("dev_dashboard") }) {
                            Icon(
                                Icons.Default.Settings,
                                "Settings",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(20.dp),
                            )
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(hostState = snackbarHostState) },
        bottomBar = {
            if (isTopLevel) {
                NavigationBar {
                    topLevelScreens.forEach { screen ->
                        val selected = currentRoute == screen.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navController.navigate(screen.route) {
                                    popUpTo(navController.graph.startDestinationId) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(screen.icon, screen.label) },
                            label = { Text(screen.label, style = MaterialTheme.typography.labelSmall) },
                            modifier = Modifier.testTag("nav_${screen.route}"),
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        // Smooth fade for tab switches (top-level screens)
        val tabEnter: AnimatedContentTransitionScope<*>.() -> EnterTransition = {
            fadeIn(tween(250))
        }
        val tabExit: AnimatedContentTransitionScope<*>.() -> ExitTransition = {
            fadeOut(tween(250))
        }

        // iOS-style horizontal slide for push/pop screens
        val slideInFromRight: AnimatedContentTransitionScope<*>.() -> EnterTransition = {
            fadeIn(tween(300)) + slideInHorizontally(tween(300)) { it / 3 }
        }
        val slideOutToRight: AnimatedContentTransitionScope<*>.() -> ExitTransition = {
            fadeOut(tween(300)) + slideOutHorizontally(tween(300)) { it / 3 }
        }
        val slideOutToLeft: AnimatedContentTransitionScope<*>.() -> ExitTransition = {
            fadeOut(tween(300)) + slideOutHorizontally(tween(300)) { -it / 3 }
        }
        val slideInFromLeft: AnimatedContentTransitionScope<*>.() -> EnterTransition = {
            fadeIn(tween(300)) + slideInHorizontally(tween(300)) { -it / 3 }
        }

        NavHost(
            navController = navController,
            startDestination = Screen.Agent.route,
            modifier = Modifier.padding(innerPadding),
            enterTransition = tabEnter,
            exitTransition = tabExit,
            popEnterTransition = tabEnter,
            popExitTransition = tabExit,
        ) {
            composable(Screen.Agent.route) { AgentScreen() }
            composable(Screen.Health.route) { HealthScreen() }
            composable(Screen.Schedule.route) { ScheduleScreen() }
            composable(Screen.Journal.route) { JournalScreen() }
            composable(Screen.Memory.route) { MemoryScreen() }
            composable(
                "dev_dashboard",
                enterTransition = slideInFromRight,
                exitTransition = slideOutToLeft,
                popEnterTransition = slideInFromLeft,
                popExitTransition = slideOutToRight,
            ) {
                DevDashboardRoute(onBackClick = { navController.popBackStack() })
            }
        }
    }
}
