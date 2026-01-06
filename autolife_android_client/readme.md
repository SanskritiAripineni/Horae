# AutoLife: Automated Journaling Agent

This Android application reproduces the core methodology of the research paper **"AutoLife: Automatic Life Journaling with Smartphones and LLMs"** (arXiv:2412.15714). It utilizes on-device sensors, Context Fusion, and the Gemini LLM to automatically infer and log the user's daily activities and context.

## **Project Status: Paper Reproduction**

We have successfully implemented the key components of the "AutoLife" system as described in the methodology:

| Feature Area | Component | Implementation Status | Description |
|---|---|---|---|
| **Data Collection** | **Sensors** | ✅ **Implemented** | Accelerometer, Gyroscope, Barometer, Step Counter. |
| | **Duty Cycle** | ✅ **Active** | 1 minute cycle (**10s** Active / 50s Idle). |
| **Motion Context** | **Rule-Based Classification** | ✅ **Implemented** | Detects Stationary, Walking, Running, Vehicle, Elevator/Escalator. |
| **Location Context** | **Map VLM** | ✅ **Implemented** | Fetches 250x250m Google Static Map images and uses **Gemini 2.5** (VLM) to infer location context (e.g., "Park", "Residential"). |
| | **WiFi Analysis** | ✅ **Implemented** | Infers venue types from nearby SSIDs. |
| **Context Fusion** | **Multi-Modal Calibration** | ✅ **Implemented** | Performs "Motion Calibration" by fusing visual location context with motion sensor data (e.g., Water + High Speed = "Ferry", Highway + High Speed = "Car"). |
| **Journaling** | **Objective Narrative** | ✅ **Implemented** | Generates concise, objective daily journals using the specific "Reasoning-Summary" prompt pattern from the paper. |

---

## **Key Features**

### 1. **Sequential Motion & Location Analysis (`SequentialMotionLocationAnalyzer.kt`)**
The app orchestrates a sophisticated pipeline that mirrors the paper's "Sequential Analysis" approach:
1.  **Motion Phase**: Collects raw sensor data to classify basic movement (e.g., "Stationary").
2.  **Location Phase**: Captures a satellite map image of the current location and uses Gemini Vision to describe the environment (e.g., "Built environment, commercial district").
3.  **Fusion Phase**: Fuses the motion and location data. It calibrates the motion based on the visual context (e.g., "Stationary" in a "Gym" -> "Resting between sets").

### 2. **Map Visual-Language Model (VLM)**
Visual context is critical for understanding "where" a user is. The app:
-   Downloads a high-res static map image.
-   Prompts Gemini to identify "transportation infrastructure", "natural features", and "built environment".
-   This provides a much richer context than simple GPS coordinates or reverse geocoding.

### 3. **Objective Journal Generation**
The `JournalGenerator` creates persistent life journals that are:
-   **Concise**: Summarizes 15-minute blocks into single sentences.
-   **Objective**: Removes subjective language (e.g., "enjoyed a coffee" -> "visited a coffee shop").
-   **Inferred**: Deduces high-level activities (e.g., "Commmuting") from low-level signals.

---

## **Setup & Configuration**

### **Prerequisites**
-   Android Studio Ladybug or newer.
-   **Gemini API Key** (with access to Flash 2.5 models).
-   **Google Maps Static API Key**.

### **Configuration Steps**
1.  **Get API Keys**:
    -   Gemini: [Google AI Studio](https://aistudio.google.com/)
    -   Maps: [Google Cloud Console](https://console.cloud.google.com/)
2.  **Local Properties**: Open `local.properties` in the project root:
    ```properties
    GEMINI_API_KEY=your_gemini_key
    MAPS_API_KEY=your_maps_key
    ```
3.  **Build & Run**:
    -   Sync Gradle.
    -   Run on a physical device (Emulators often lack necessary sensors).
    -   **Grant Permissions**: `Location`, `Physical Activity`, and `Notification`.

## **Architecture**
-   **Language**: Kotlin
-   **AI Model**: Gemini 2.5 Flash Lite (via `google-generativeai` SDK)
-   **Database**: Room (SQLite)
-   **Concurrency**: Kotlin Coroutines (`Dispatchers.Default` for analysis)

## **Project Structure**
-   `SequentialMotionLocationAnalyzer.kt`: The core engine orchestrating the Motion -> Map VLM -> Fusion pipeline.
-   `LocationAnalyzer.kt`: Handles Map image fetching and VLM analysis.
-   `ContextFusionAnalyzer.kt`: Fuses motion and location streams.
-   `JournalGenerator.kt`: Generates the final daily journal entries.
