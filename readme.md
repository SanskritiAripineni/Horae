# AutoLife: Automated Journaling Agent

This Android application works to reproduce the core methodology of the research paper **"AutoLife: Automatic Life Journaling with Smartphones and LLMs"** (arXiv:2412.15714). It utilizes on-device sensors and the Gemini LLM to automatically infer and log the user's daily activities and context.

## **Project Status: Paper Reproduction**

We are actively working to reproduce the "AutoLife" system. Below is a detailed comparison of the implementation status against the methodology described in the research paper.

| Feature Area | Component | Implementation Status | Implementation vs Paper Specification |
|---|---|---|---|
| **Data Collection** | **Sensors** | ✅ **Implemented** | **Implemented:** Accelerometer, Gyroscope, Barometer, Step Counter. <br> **Paper:** Matches spec. |
| | **Duty Cycle** | ⚠️ **Modified** | **Current:** 1 minute cycle (**10s** Active / 50s Idle). <br> **Paper:** 1 minute cycle (**15s** Active / 45s Idle). |
| **Motion Context** | **Rule-Based Classification** | ✅ **Implemented** | **Implemented:** Detects Stationary, Walking, Running, cycling, Vehicle, Escalator/Elevator. Matches "Algorithm 1" in paper. |
| | **Altitude Tracking** | ✅ **Implemented** | Uses Barometer for vertical transport detection (Elevator/Escalator). |
| **Location Context** | **Method A: Visual Map** | ❌ **Not Implemented** | **Paper:** Fetches 250x250m Google Static Map (Zoom 18) and uses VLM to infer zone (e.g., "Residential"). <br> **Current:** Missing entirely. |
| | **Method B: WiFi Analysis** | ✅ **Implemented** | **Paper:** Uses LLM to infer venue from SSIDs. <br> **Current:** Implemented with **Gemini 2.5 Flash Lite**. |
| **Context Fusion** | **Multi-Modal Fusion** | ⚠️ **Partial** | **Paper:** Fuses Map + SSID + Motion using LLM to resolve ambiguities (e.g., High speed + Highway = Vehicle). <br> **Current:** Basic concatenation implemented (`ContextFusionAnalyzer`), but disabled in main loop. |
| **Journaling** | **Temporal Aggregation** | ❌ **Not Implemented** | **Paper:** Aggregates **15** one-minute segments into a single "Context Block" before generating a journal. <br> **Current:** Logs individual 1-minute events. |
| | **Narrative Generation** | ⚠️ **Basic** | **Paper:** Uses "Reasoning-Summary" prompt pattern and subjectivity removal pass. <br> **Current:** Simple generation prompt; lacks multi-step refinement. |

---

## **Key Features**

### 1. **Intelligent Motion Detection (`MotionDetector.kt`)**
The app continuously monitors device sensors to classify activity. Unlike basic step counters, it uses a multi-factor rule engine:
- **Stationary**: Low steps + Low acceleration.
- **Elevator/Escalator**: Altitude change with low steps.
- **Cycling/Vehicle**: Speed thresholds (GPS) combined with step frequency.

### 2. **LLM-Powered Location Context (`LocationAnalyzer.kt`)**
Instead of just logging coordinates, the app scans nearby WiFi networks (SSIDs) and sends them to the **Gemini LLM**.
- **Input**: "Starbucks_Guest", "Google_Internal", "My_iPhone"
- **Output**: "Coffee Shop" or "Office Environment"
- *Note: This runs on the IO thread to prevent UI blocking.*

### 3. **Background Service (`AutoLifeService.kt`)**
- Runs as a **Foreground Service** with a persistent notification ("Logging your life context...").
- Wakes up every **60 seconds** to perform a sensor analysis burst.
- Logs results to a local Room database.

---

## **Setup & Configuration**

### **Prerequisites**
- Android Studio Ladybug or newer.
- A **Gemini API Key**.

### **Configuration Steps**
1. **Get an API Key**: Visit [Google AI Studio](https://aistudio.google.com/) to get your Gemini API key.
2. **Local Properties**: Open `local.properties` in the project root and add your key:
   ```properties
   GEMINI_API_KEY=your_api_key_here
   ```
3. **Build & Run**:
   - Sync Gradle.
   - Run on a physical device (Emulators often lack necessary sensors like Accelerometer/Wifi).
   - **Grant Permissions**: The app requires `Location`, `Physical Activity`, and `Notification` permissions.

## **Architecture**

- **Language**: Kotlin
- **AI Model**: Gemini 2.5 Flash Lite (via `google-generativeai` SDK)
- **Database**: Room (SQLite)
- **Concurrency**: Kotlin Coroutines (`Dispatchers.Default` for analysis, `Dispatchers.Main` for UI updates)

## **Project Structure**

- `MotionDetector.kt`: Raw sensor data processing and rule-based classification.
- `WifiScanner.kt`: Scans visible SSIDs (requires Location permission).
- `LocationAnalyzer.kt`: Interfaces with Gemini to predict location from WiFi.
- `SequentialMotionLocationAnalyzer.kt`: Orchestrates the analysis pipeline (Motion -> Location).
- `AutoLifeService.kt`: Background service managing the duty cycle.
