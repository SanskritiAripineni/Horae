package com.google.mediapipe.examples.llminference.ui

import android.content.Intent
import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Info
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.mediapipe.examples.llminference.AutoLifeApp
import com.google.mediapipe.examples.llminference.AutoLifeService
import com.google.mediapipe.examples.llminference.data.JournalEntry
import com.google.mediapipe.examples.llminference.data.SensorLog
import kotlinx.coroutines.flow.Flow
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class DashboardViewModel(application: android.app.Application) : androidx.lifecycle.AndroidViewModel(application) {
    private val dao = (application as AutoLifeApp).database.logDao()
    
    val recentLogs: Flow<List<SensorLog>> = dao.observeRecentLogs()
    // val journals: Flow<List<JournalEntry>> = dao.observeJournals() // Not implemented in UI yet but flow exists
    
    fun clearLogs() {
        viewModelScope.launch {
            dao.deleteAllLogs()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel = viewModel()
) {
    val context = LocalContext.current
    val logs by viewModel.recentLogs.collectAsState(initial = emptyList())
    // 0: Main Dashboard, 1: Developer Dashboard
    var currentScreen by remember { mutableStateOf(0) }
    var selectedTab by remember { mutableStateOf(0) }
    var showServiceInfo by remember { mutableStateOf(false) }

    // REAL Service State from Repository
    val isServiceRunning by com.google.mediapipe.examples.llminference.data.DebugRepository.isServiceRunning.collectAsStateWithLifecycle()
    
    if (showServiceInfo) {
        AlertDialog(
            onDismissRequest = { showServiceInfo = false },
            title = { Text("AutoLife Service Info") },
            text = { 
                Text("The AutoLife background service runs a 15-second sensor analysis cycle every minute to save battery.\n\nIt collects:\n- Motion Data (Accelerometer, Steps)\n- Location Data (SSIDs, Map Images)\n\nIt then fuses this data to generate context logs.") 
            },
            confirmButton = {
                TextButton(onClick = { showServiceInfo = false }) { Text("OK") }
            }
        )
    }

    if (currentScreen == 1) {
        DevDashboardScreen(
            onBackClick = { currentScreen = 0 }
        )
    } else {
        Scaffold(
            topBar = {
                Column {
                    TopAppBar(
                        title = { Text("AutoLife Research") },
                        actions = {
                            ServiceControl(
                                isServiceRunning = isServiceRunning,
                                onToggle = { shouldStart ->
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
                                }
                            )
                            IconButton(onClick = { showServiceInfo = true }) {
                                Icon(
                                    imageVector = Icons.Default.Info,
                                    contentDescription = "Service Info"
                                )
                            }
                            IconButton(onClick = { viewModel.clearLogs() }) {
                                Icon(
                                    imageVector = Icons.Default.Delete,
                                    contentDescription = "Clear Logs"
                                )
                            }
                            IconButton(onClick = { currentScreen = 1 }) {
                                Icon(
                                    imageVector = Icons.Default.Settings,
                                    contentDescription = "Developer Dashboard"
                                )
                            }
                        }
                    )
                    TabRow(selectedTabIndex = selectedTab) {
                        Tab(selected = selectedTab == 0, onClick = { selectedTab = 0 }, text = { Text("Live Logs") })
                        Tab(selected = selectedTab == 1, onClick = { selectedTab = 1 }, text = { Text("Journals") })
                    }
                }
            }
        ) { padding ->
            Box(modifier = Modifier.padding(padding)) {
                if (selectedTab == 0) {
                    LogsList(logs)
                } else {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("Journal Generation Coming Soon")
                    }
                }
            }
        }
    }
}

@Composable
fun ServiceControl(isServiceRunning: Boolean, onToggle: (Boolean) -> Unit) {
    Row(modifier = Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Text("Service: ", style = MaterialTheme.typography.labelLarge)
        Switch(
            checked = isServiceRunning,
            onCheckedChange = { 
                onToggle(it) 
            }
        )
    }
}

// Helper to check if service is running (not accurate without ActivityManager check, keeping simple)
fun isServiceRunning(context: android.content.Context): Boolean {
    // Placeholder: In a real app we'd check ActivityManager or use a strict Service binding.
    return false 
}

@Composable
fun LogsList(logs: List<SensorLog>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Color(0xFFF5F5F5)),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(logs) { log ->
            LogCard(log)
        }
    }
}

@Composable
fun LogCard(log: SensorLog) {
    Card(
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(modifier = Modifier.padding(12.dp).fillMaxWidth()) {
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = log.type,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = formatTime(log.timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = log.content,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 10
            )
        }
    }
}

fun formatTime(timestamp: Long): String {
    val sdf = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
    return sdf.format(Date(timestamp))
}
