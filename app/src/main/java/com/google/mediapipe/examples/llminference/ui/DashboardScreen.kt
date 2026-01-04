package com.google.mediapipe.examples.llminference.ui

import android.content.Intent
import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel = viewModel()
) {
    val context = LocalContext.current
    val logs by viewModel.recentLogs.collectAsState(initial = emptyList())
    var selectedTab by remember { mutableStateOf(0) }
    
    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = { Text("AutoLife Research") },
                    actions = {
                        ServiceControl(
                            isServiceRunning = isServiceRunning(context),
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

@Composable
fun ServiceControl(isServiceRunning: Boolean, onToggle: (Boolean) -> Unit) {
    // This is a naive check (stateless UI), actual service state sync is harder without binding.
    // For research prototype, we just provide buttons.
    var runningState by remember { mutableStateOf(false) } // Local toggle state for UI feedback

    Row(modifier = Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Text("Service: ", style = MaterialTheme.typography.labelLarge)
        Switch(
            checked = runningState,
            onCheckedChange = { 
                runningState = it
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
