package com.autolife.composeapp.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.autolife.composeapp.ui.components.withSerif
import androidx.navigation.NavBackStackEntry
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
    val topLevelScreens = listOf(
        Screen.Agent, Screen.Health, Screen.Schedule, Screen.Journal, Screen.Memory,
    )
    val backStack by navController.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    val serviceState by PlatformStateProvider.serviceState.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(Unit) {
        SnackbarBus.messages.collect { msg ->
            snackbarHostState.showSnackbar(msg)
        }
    }

    val isTopLevel = topLevelScreens.any { it.route == currentRoute }
    val topBarTitle = when (currentRoute) {
        Screen.Agent.route -> "RIDE Agent"
        Screen.Health.route -> "Health"
        Screen.Schedule.route -> "Schedule"
        Screen.Journal.route -> "Journal"
        Screen.Memory.route -> "Memory"
        else -> "RIDE"
    }

    fun navigateTopLevel(route: String) {
        navController.navigate(route) {
            popUpTo(navController.graph.startDestinationId) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun routeIndex(route: String?): Int = topLevelScreens.indexOfFirst { it.route == route }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        topBarTitle,
                        style = MaterialTheme.typography.titleLarge.withSerif(),
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                    actionIconContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    navigationIconContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                ),
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
                                Icons.Default.BugReport,
                                "Dev tools",
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
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.background,
                    contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    tonalElevation = 0.dp,
                ) {
                    topLevelScreens.forEach { screen ->
                        val selected = currentRoute == screen.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navigateTopLevel(screen.route)
                            },
                            icon = { Icon(screen.icon, screen.label, modifier = Modifier.size(24.dp)) },
                            label = { Text(screen.label, style = MaterialTheme.typography.labelSmall) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = MaterialTheme.colorScheme.onPrimary,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                indicatorColor = MaterialTheme.colorScheme.primary,
                                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            ),
                            modifier = Modifier.testTag("nav_${screen.route}"),
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        // Smooth fade for tab switches (top-level screens)
        val topLevelEnter: AnimatedContentTransitionScope<NavBackStackEntry>.() -> EnterTransition = {
            val initial = routeIndex(initialState.destination.route)
            val target = routeIndex(targetState.destination.route)
            if (initial >= 0 && target >= 0) {
                slideInHorizontally(tween(280)) { fullWidth ->
                    if (target > initial) fullWidth / 3 else -fullWidth / 3
                } + fadeIn(tween(280))
            } else {
                fadeIn(tween(250))
            }
        }
        val topLevelExit: AnimatedContentTransitionScope<NavBackStackEntry>.() -> ExitTransition = {
            val initial = routeIndex(initialState.destination.route)
            val target = routeIndex(targetState.destination.route)
            if (initial >= 0 && target >= 0) {
                slideOutHorizontally(tween(280)) { fullWidth ->
                    if (target > initial) -fullWidth / 3 else fullWidth / 3
                } + fadeOut(tween(280))
            } else {
                fadeOut(tween(250))
            }
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
            modifier = Modifier
                .padding(innerPadding)
                .pointerInput(currentRoute) {
                    if (!isTopLevel) return@pointerInput
                    var totalDrag = 0f
                    detectHorizontalDragGestures(
                        onHorizontalDrag = { _, dragAmount ->
                            totalDrag += dragAmount
                        },
                        onDragEnd = {
                            val currentIndex = routeIndex(currentRoute)
                            if (currentIndex < 0) return@detectHorizontalDragGestures
                            val threshold = 72.dp.toPx()
                            when {
                                totalDrag <= -threshold && currentIndex < topLevelScreens.lastIndex ->
                                    navigateTopLevel(topLevelScreens[currentIndex + 1].route)
                                totalDrag >= threshold && currentIndex > 0 ->
                                    navigateTopLevel(topLevelScreens[currentIndex - 1].route)
                            }
                            totalDrag = 0f
                        },
                        onDragCancel = {
                            totalDrag = 0f
                        },
                    )
                },
            enterTransition = topLevelEnter,
            exitTransition = topLevelExit,
            popEnterTransition = topLevelEnter,
            popExitTransition = topLevelExit,
        ) {
            composable(Screen.Agent.route) {
                AgentScreen(
                    onOpenHealth = { navigateTopLevel(Screen.Health.route) },
                    onServiceToggle = onServiceToggle,
                )
            }
            composable(Screen.Health.route) {
                HealthScreen(
                    onOpenAgent = { navigateTopLevel(Screen.Agent.route) },
                )
            }
            composable(Screen.Schedule.route) { ScheduleScreen(onOpenAgent = { navigateTopLevel(Screen.Agent.route) }) }
            composable(Screen.Journal.route) { JournalScreen(onServiceToggle = onServiceToggle) }
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
