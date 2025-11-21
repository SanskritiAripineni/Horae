package com.google.mediapipe.examples.llminference

import android.os.Build
import android.Manifest
import android.content.ComponentCallbacks2
import android.os.Bundle
import android.os.StrictMode
import android.util.Log
import android.view.Choreographer
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.mediapipe.examples.llminference.server.OllamaClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL


class MainViewModel : ViewModel() {
    private val _chatResponse = MutableStateFlow<String?>(null)
    val chatResponse = _chatResponse.asStateFlow()

    // Base URL logic: 10.0.2.2 for emulator, 127.0.0.1 for phone (with adb reverse)
    private val isEmulator =
        Build.FINGERPRINT.contains("generic") || Build.MODEL.contains("sdk", ignoreCase = true)
    private val ollamaBase = if (isEmulator) "http://10.0.2.2:11434" else "http://127.0.0.1:11434"

    fun sendMessage(msg: String) {
        viewModelScope.launch {
            _chatResponse.value = "Loading..."
            val result = runCatching { callOllama(ollamaBase, "gemma3:1b", msg) }
            _chatResponse.value = result.getOrElse { e -> "Error: ${e.message}" }
        }
    }

    private suspend fun callOllama(base: String, model: String, prompt: String): String =
        withContext(Dispatchers.IO) {
            val url = URL("$base/api/generate")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = 10_000
                readTimeout = 60_000
                setRequestProperty("Content-Type", "application/json")
            }

            val payload = JSONObject().apply {
                put("model", model)
                put("prompt", prompt)
                put("stream", false)
            }.toString()

            conn.outputStream.use { it.write(payload.toByteArray(Charsets.UTF_8)) }

            val code = conn.responseCode
            val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                .bufferedReader().use { it.readText() }

            // Try to extract the "response" field; otherwise return the raw body
            return@withContext runCatching {
                JSONObject(body).optString("response").ifEmpty { body }
            }.getOrDefault(body)
        }
}


// ----- ORIGINAL CODE ---- ViewModel
//class MainViewModel : ViewModel() {
//    private val _chatResponse = MutableStateFlow<String?>(null)
//    val chatResponse = _chatResponse.asStateFlow()
//
//    // Initialize OllamaClient with your server's base URL
//    val isEmulator = Build.FINGERPRINT.contains("generic") || Build.MODEL.contains("sdk")
//    val ollamaClient = if (isEmulator) "http://10.0.2.2:11434" else "http://127.0.0.1:11434"
//    // Use 10.0.2.2 for Android Emulator
//    // For physical device, point to your computer's local IP address, e.g.:
////     private val ollamaClient = OllamaClient("http://<your-machine-ip>:11434/")
//
//    fun sendMessage(message: String) {
//        viewModelScope.launch {
//            try {
//                _chatResponse.value = "Loading..."
//                val response = ollamaClient.chat(
//                    model = "gemma3:1b",  // or your preferred model
//                    message = message
//                )
//
//                _chatResponse.value = when {
//                    response.isSuccess -> response.getOrNull()?.message?.content ?: "Empty response"
//                    else -> "Error: ${response.exceptionOrNull()?.message}"
//                }
//            } catch (e: Exception) {
////                _chatResponse.value = "Error: ${e.message}"
//                _chatResponse.value = when {
//                    response.isSuccess -> response.getOrNull()?.toString() ?: "Empty response"
//                    else -> "Error: ${response.exceptionOrNull()?.message}"
//                }
//            }
//        }
//    }
//}

@Composable
fun rememberMainViewModel(): MainViewModel {
    return viewModel()
}

class MainActivity : ComponentActivity() {

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        // Avoid manual GC; rely on system. Could add adaptive logging if needed.
        if (level == ComponentCallbacks2.TRIM_MEMORY_RUNNING_CRITICAL) {
            Log.w("MainActivity", "Memory critical: level=$level")
        }
    }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { }

//    override fun onCreate(savedInstanceState: Bundle?) {
//        super.onCreate(savedInstanceState)
//        requestPermissionLauncher.launch(
//            arrayOf(
//                Manifest.permission.ACCESS_FINE_LOCATION,
//                Manifest.permission.ACTIVITY_RECOGNITION,
//                Manifest.permission.INTERNET
//            )
//        )
//
//        setContent {
//            MaterialTheme {
//                MainScreen()
//            }
//        }
//    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val isDebug = (applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
        if (isDebug) {
            StrictMode.setThreadPolicy(
                StrictMode.ThreadPolicy.Builder()
                    .detectAll()
                    .penaltyLog()
                    .build()
            )
            StrictMode.setVmPolicy(
                StrictMode.VmPolicy.Builder()
                    .detectLeakedClosableObjects()
                    .penaltyLog()
                    .build()
            )
        }
        setupFrameMonitor()

        // Build the permission list based on OS version
        val perms = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACTIVITY_RECOGNITION
        )
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            // Android 13+ needs this for Wi-Fi scans / nearby devices discovery
            perms += Manifest.permission.NEARBY_WIFI_DEVICES
        }

        requestPermissionLauncher.launch(perms.toTypedArray())

        setContent {
            MaterialTheme {
                MainScreen()
            }
        }
    }

    private fun setupFrameMonitor() {
        // Log long frames to help diagnose UI stalls / input timeouts
        val choreographer = Choreographer.getInstance()
        val frameCallback = object : Choreographer.FrameCallback {
            private var lastFrameTimeNanos: Long = 0L
            override fun doFrame(frameTimeNanos: Long) {
                if (lastFrameTimeNanos != 0L) {
                    val diffMs = (frameTimeNanos - lastFrameTimeNanos) / 1_000_000
                    if (diffMs > 32) { // >2 frame intervals at 60Hz
                        Log.w("FrameMonitor", "Long frame: ${diffMs}ms")
                    }
                }
                lastFrameTimeNanos = frameTimeNanos
                choreographer.postFrameCallback(this)
            }
        }
        choreographer.postFrameCallback(frameCallback)
    }

}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {
    val context = LocalContext.current
    val viewModel = rememberMainViewModel()
    var currentAnalysis by remember { mutableStateOf<String?>(null) }
    var currentPhase by remember { mutableStateOf(SequentialMotionLocationAnalyzer.AnalysisPhase.NONE) }
    var isAnalyzing by remember { mutableStateOf(false) }
    var isFusing by remember { mutableStateOf(false) }
    var fusionResult by remember { mutableStateOf<String?>(null) }
    var memoryInfo by remember { mutableStateOf(MemoryMonitor.getMemoryInfo(context)) }

//    val analyzer = remember { SequentialMotionLocationAnalyzer(context) }
//    val fusionAnalyzer = remember { ContextFusionAnalyzer(context) }

    var analyzer by remember { mutableStateOf<SequentialMotionLocationAnalyzer?>(null) }
    var fusionAnalyzer by remember { mutableStateOf<ContextFusionAnalyzer?>(null) }

//    // In Start Analysis onClick:
//    if (analyzer == null) analyzer = SequentialMotionLocationAnalyzer(context)
//    // In Test Fusion onClick:
//    if (fusionAnalyzer == null) fusionAnalyzer = ContextFusionAnalyzer(context)




    val scope = rememberCoroutineScope()
    val chatResponse = viewModel.chatResponse.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        // Fixed content section
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Memory Monitor
            MemoryMonitorCard(memoryInfo = memoryInfo)

            // Sequential Analysis Card
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("Sequential Analysis", style = MaterialTheme.typography.titleMedium)

                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            if (!isAnalyzing) {
                                if (analyzer == null) analyzer = SequentialMotionLocationAnalyzer(context)
                                isAnalyzing = true
                                scope.launch {
                                    memoryInfo = MemoryMonitor.getMemoryInfo(context)
                                    analyzer!!.startAnalysis { result, phase ->
                                        currentAnalysis = result
                                        currentPhase = phase
                                        scope.launch { memoryInfo = MemoryMonitor.getMemoryInfo(context) }
                                        if (phase == SequentialMotionLocationAnalyzer.AnalysisPhase.COMPLETE) {
                                            isAnalyzing = false
                                        }
                                    }
                                }
                            } else {
                                analyzer?.stopAnalysis()
                                isAnalyzing = false
                            }
                        }
                    ) {
                        Text(
                            when(currentPhase) {
                                SequentialMotionLocationAnalyzer.AnalysisPhase.MOTION -> "Motion Detection in Progress..."
                                SequentialMotionLocationAnalyzer.AnalysisPhase.LOCATION -> "Location Analysis in Progress..."
                                SequentialMotionLocationAnalyzer.AnalysisPhase.COMPLETE -> "Analysis Complete"
                                else -> "Start Analysis"
                            }
                        )
                    }

                    if (isAnalyzing) {
                        LinearProgressIndicator(
                            modifier = Modifier.fillMaxWidth(),
                            progress = when(currentPhase) {
                                SequentialMotionLocationAnalyzer.AnalysisPhase.MOTION -> 0.3f
                                SequentialMotionLocationAnalyzer.AnalysisPhase.LOCATION -> 0.7f
                                SequentialMotionLocationAnalyzer.AnalysisPhase.COMPLETE -> 1.0f
                                else -> 0f
                            }
                        )
                    }
                }
            }

            // Fusion Test Card
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("Test Context Fusion", style = MaterialTheme.typography.titleMedium)

                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !isFusing,
                        onClick = {
                            scope.launch {
                                if (fusionAnalyzer == null) fusionAnalyzer = ContextFusionAnalyzer(context)
                                isFusing = true
                                memoryInfo = MemoryMonitor.getMemoryInfo(context)
                                fusionResult = fusionAnalyzer!!.performFusion()
                                memoryInfo = MemoryMonitor.getMemoryInfo(context)
                                isFusing = false
                            }
                        }
                    ) {
                        Text(if (isFusing) "Fusing Contexts..." else "Test Fusion")
                    }

                    if (isFusing) {
                        LinearProgressIndicator(
                            modifier = Modifier.fillMaxWidth(),
                            progress = 0.5f
                        )
                    }
                }
            }

            // Ollama Test Card
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("Test Ollama API", style = MaterialTheme.typography.titleMedium)

                    Button(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            viewModel.sendMessage("Hello, how are you?")
                        }
                    ) {
                        Text("Test Ollama")
                    }

                    chatResponse.value?.let { response ->
                        if (response == "Loading...") {
                            LinearProgressIndicator(
                                modifier = Modifier.fillMaxWidth(),
                                progress = 0.5f
                            )
                        }
                    }
                }
            }
        }

        // Scrollable content section
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(horizontal = 16.dp)
        ) {
            Card(
                modifier = Modifier.fillMaxSize()
            ) {
                Box(
                    modifier = Modifier
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Column {
                        currentAnalysis?.let {
                            Text(
                                text = it,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }

                        fusionResult?.let {
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = "Fusion Result:\n$it",
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }

                        chatResponse.value?.let { response ->
                            if (response != "Loading...") {
                                Spacer(modifier = Modifier.height(16.dp))
                                Text(
                                    text = "Ollama Response:\n$response",
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MemoryMonitorCard(memoryInfo: MemoryMonitor.MemoryInfo) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "Memory Monitor",
                    style = MaterialTheme.typography.titleSmall
                )
                Text(
                    text = "Java: ${memoryInfo.usedMemoryMB}MB / ${memoryInfo.maxHeapSizeMB}MB",
                    style = MaterialTheme.typography.bodySmall
                )
            }

            Text(
                text = "Native Heap: ${memoryInfo.nativeHeapMB}MB",
                style = MaterialTheme.typography.bodySmall
            )

            val rssProgress = (memoryInfo.totalRSSMB.toFloat() / 6000f).coerceIn(0f, 1f)
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Total RSS Memory",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        text = "${memoryInfo.totalRSSMB}MB",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                LinearProgressIndicator(
                    progress = rssProgress,
                    modifier = Modifier.fillMaxWidth(),
                    color = when {
                        rssProgress > 0.8f -> MaterialTheme.colorScheme.error
                        rssProgress > 0.6f -> MaterialTheme.colorScheme.secondary
                        else -> MaterialTheme.colorScheme.primary
                    }
                )
            }

            Text(
                text = "Total PSS: ${memoryInfo.totalPSSMB}MB",
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}
