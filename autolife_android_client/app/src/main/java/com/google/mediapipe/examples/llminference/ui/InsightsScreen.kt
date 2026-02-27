package com.google.mediapipe.examples.llminference.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mediapipe.examples.llminference.AutoLifeApp
import com.google.mediapipe.examples.llminference.network.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

class InsightsViewModel(application: android.app.Application) : androidx.lifecycle.AndroidViewModel(application) {
    private val dao = (application as AutoLifeApp).database.logDao()
    
    var isLoading by mutableStateOf(false)
    var analysisResult by mutableStateOf<ProcessJournalsResponse?>(null)
    var errorMessage by mutableStateOf<String?>(null)

    // Calendar selection state
    var selectedProposals = mutableStateListOf<Map<String, Any>>()

    fun analyzeJournals() {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                // 1. Get recent journals from DB
                val dbJournals = dao.getAllJournals().takeLast(10)
                if (dbJournals.isEmpty()) {
                    errorMessage = "No journals found in database yet. Let AutoLife run for a bit."
                    isLoading = false
                    return@launch
                }

                // 2. Map to Api model
                val sdf = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                val apiJournals = dbJournals.mapIndexed { index, j ->
                    ApiJournalEntry(
                        id = j.id.toString(),
                        entry_number = index + 1,
                        created_at = sdf.format(Date(j.createdTimestamp)),
                        period = "Auto-generated sequence",
                        content = j.content,
                        timestamp = sdf.format(Date(j.createdTimestamp))
                    )
                }

                val request = ProcessJournalsRequest(journals = apiJournals)
                
                // 3. Make API call
                val response = BackendApiClient.apiService.processJournals(request)
                analysisResult = response
                
                // Reset selections
                selectedProposals.clear()
                
            } catch (e: Exception) {
                errorMessage = "Network error: ${e.message}\nEnsure Python API is running on localhost:8000"
            } finally {
                isLoading = false
            }
        }
    }

    fun applySelectedCalendarChanges() {
        if (selectedProposals.isEmpty()) return
        viewModelScope.launch {
            isLoading = true
            try {
                val request = ApplyCalendarRequest(changes = selectedProposals)
                val response = BackendApiClient.apiService.applyCalendar(request)
                errorMessage = "Successfully applied ${response.applied.size} changes!"
                // Remove applied from the list so user doesn't double-apply
                analysisResult = analysisResult?.copy(
                    proposed_changes = analysisResult!!.proposed_changes.filter { it !in selectedProposals }
                )
                selectedProposals.clear()
            } catch (e: Exception) {
                errorMessage = "Failed to apply calendar changes: ${e.message}"
            } finally {
                isLoading = false
            }
        }
    }
}

@Composable
fun InsightsScreen(viewModel: InsightsViewModel = viewModel()) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Button(
            onClick = { viewModel.analyzeJournals() },
            modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
            enabled = !viewModel.isLoading
        ) {
            Text(if (viewModel.isLoading) "Analyzing..." else "Analyze Recent Journals")
        }

        if (viewModel.errorMessage != null) {
            Text(
                text = viewModel.errorMessage!!,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(bottom = 16.dp)
            )
        }

        viewModel.analysisResult?.let { result ->
            LazyColumn(modifier = Modifier.fillMaxWidth()) {
                item {
                    Text("Mental Health Summary", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Summary: ${result.journal_summary ?: "N/A"}", style = MaterialTheme.typography.bodyMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                }

                result.mental_health?.let { mh ->
                    item {
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Risk Level: ${mh.risk_level.uppercase()}", fontWeight = FontWeight.Bold)
                                Text("Estimated PHQ-4: ${mh.estimated_phq4}/12", fontWeight = FontWeight.SemiBold)
                                Spacer(modifier = Modifier.height(8.dp))
                                Text("Key Concerns:", fontWeight = FontWeight.Bold)
                                mh.key_concerns.forEach { Text("- $it", style = MaterialTheme.typography.bodySmall) }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text("Positives:", fontWeight = FontWeight.Bold)
                                mh.positive_indicators.forEach { Text("+ $it", style = MaterialTheme.typography.bodySmall) }
                            }
                        }
                    }
                }

                if (result.recommendations.isNotEmpty()) {
                    item {
                        Text("Recommendations", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 16.dp))
                    }
                    items(result.recommendations) { rec ->
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text("[${rec.category}] ${rec.action}", fontWeight = FontWeight.Bold)
                                if (rec.when_to_do != null) Text("When: ${rec.when_to_do}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }

                if (result.proposed_changes.isNotEmpty()) {
                    item {
                        Text("Calendar Optimization Proposals", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 16.dp, bottom = 8.dp))
                        Text("Select changes to apply to your Google Calendar.", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                    }

                    items(result.proposed_changes) { change ->
                        val isSelected = viewModel.selectedProposals.contains(change)
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(
                                    checked = isSelected,
                                    onCheckedChange = { checked ->
                                        if (checked) viewModel.selectedProposals.add(change)
                                        else viewModel.selectedProposals.remove(change)
                                    }
                                )
                                Column(modifier = Modifier.padding(start = 8.dp)) {
                                    Text(change["title"] as? String ?: "Event", fontWeight = FontWeight.Bold)
                                    Text("Time: ${change["start_time"]}", style = MaterialTheme.typography.bodySmall)
                                    val desc = change["description"] as? String
                                    if (!desc.isNullOrEmpty()) {
                                        Text(desc, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                                    }
                                }
                            }
                        }
                    }

                    item {
                        Button(
                            onClick = { viewModel.applySelectedCalendarChanges() },
                            modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp),
                            enabled = viewModel.selectedProposals.isNotEmpty() && !viewModel.isLoading
                        ) {
                            Text("Apply Selected to Calendar")
                        }
                    }
                }
            }
        }
    }
}
