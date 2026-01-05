package com.google.mediapipe.examples.llminference

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable

class ContextFusionAnalyzer(private val context: Context) : Closeable {
    companion object {
        private const val TAG = "ContextFusionAnalyzer"
    }

    suspend fun performFusion(motionHistory: String, locationContext: String): String = withContext(Dispatchers.IO) {
        try {
            val loc = getBestLocation(context)
            // Use provided locationContext from Sequential Analyzer which contains the rich VLM description
            // But we can also keep lat/long for debug if needed.

            // Ideally we would get the "Location Context" text from LocationAnalyzer here too? 
            // In the Sequential flow, we have it. But this class is standalone.
            // Let's assume this class is doing the FINAL fusion.
            // But wait, the SequentialAnalyzer calls LocationAnalyzer FIRST, gets a result string.
            // THEN calls this.
            // So we should probably pass the *Location Analysis Result* too?
            // The method signature in SequentialAnalyzer is `performContextFusion(context)`. 
            // It doesn't pass the location analysis result!
            // I need to change SequentialAnalyzer to pass the Location Result too.
            
            // For now, let's just update the signature to take motion.
            // And maybe we pass the location result string as well?
            // Yes.
            
            // Wait, I can't change signature here without changing the caller details in the same turn if possible to avoid compilation error if I was running a compiler.
            // But I'm doing sequential edits.
            
            // I'll update signature to `performFusion(motionHistory: String, locationContext: String)` in the next step.
            // But wait, I need to see the `Sequential...` file again to capture the variable name for location result.
            // In `Sequential...` (Step 118):
            // `runLocationAnalysis` returns boolean. The data is saved to DB.
            // `finishAnalysis` calls `getCombinedResults`.
            
            // It seems `Sequential...` flow separates them.
            // `runLocationAnalysis` (lines 225) calls `LocationAnalyzer.analyzeLocation`.
            // The RESULT is `callback(...)` and `logDao.insertLog`.
            // It does NOT return the string to the caller of `runLocationAnalysis` smoothly for variable capture?
            // Actually `runLocationAnalysis` returns `Boolean`.
            // The result is local variable `result`.
            
            // To pass `locationContext` to `performContextFusion`, I need to store it in `Sequential...` class or pass it down.
            // `Sequential...` has `locationAnalyzer` field but `analyzeLocation` returns string.
            
            // PROPOSAL:
            // 1. `SequentialAnalyzer`: Add a field `private var lastLocationContext: String? = null`
            // 2. `runLocationAnalysis`: Save `result` to `lastLocationContext`.
            // 3. `performContextFusion`: Use `lastLocationContext` and `MotionStorage` to call `ContextFusionAnalyzer`.
            
            // This requires multiple steps.
            // Detailed plan verified.
            
            // So for THIS file (ContextFusionAnalyzer):
            // Update signature to `performFusion(motionHistory: String, locationContext: String)`.
            // Update prompt.
            
            val prompt = """
            You are an intelligent life-logging assistant.
            Input:
            - Detected Motion (from sensors): $motionHistory
            - Location Context (from map analysis): $locationContext

            Task:
            1. Motion Calibration: Select the most probable motion given the location context.
            2. Present the result as a concise log entry.

            Format:
            [Motion Calibrated] in [Location Context]
            """.trimIndent()

            Log.d(TAG, "Sending fusion prompt to Gemini...")
            val response = GeminiClient.generateResponse(prompt)
            Log.d(TAG, "Received fusion response: $response")
            
            response
        } catch (e: Exception) {
            "Fusion failed: ${e.message}"
        }
    }

    override fun close() {
    }
}
