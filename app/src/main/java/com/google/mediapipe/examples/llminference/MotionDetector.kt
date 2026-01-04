package com.google.mediapipe.examples.llminference

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.util.Log
import kotlin.math.abs
import kotlin.math.sqrt

class MotionDetector(private val context: Context) : SensorEventListener {
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    private val motionStorage = MotionStorage(context)

    private var lastAcceleration = 0.0
    private var baselineStepCount = -1  // Store baseline when detection starts
    private var currentStepCount = 0
    private var lastAltitude = 0.0
    private var currentSpeed = 0.0
    private var lastDetectionTime = 0L
    private val DETECTION_INTERVAL_MS = 2000L  // Update every 2 seconds

    private var motionCallback: ((List<String>) -> Unit)? = null

    companion object {
        private const val TAG = "MotionDetector"
        // Adjusted thresholds for session-based step counting
        private const val STATIONARY_STEPS_THRESHOLD = 5
        private const val LIMITED_MOTION_STEPS_THRESHOLD = 15
        private const val WALKING_STEPS_THRESHOLD = 30
        private const val JOGGING_STEPS_THRESHOLD = 80
        
        private const val STATIONARY_ACCEL_THRESHOLD = 0.8
        private const val STATIONARY_SPEED_THRESHOLD = 0.5 // m/s
        private const val WALKING_SPEED_THRESHOLD = 0.5  // m/s (~1.8 km/h)
        private const val JOGGING_SPEED_MIN = 2.0  // m/s
        private const val JOGGING_SPEED_MAX = 5.0  // m/s
        private const val CYCLING_SPEED_MIN = 4.0  // m/s
        private const val VEHICLE_SPEED_MIN = 5.0  // m/s (~18 km/h)
    }

    // Function to get motion history
    fun getMotionHistory(): String? {
        return motionStorage.getMotionHistory()
    }

    // Function to clear motion history
    fun clearMotionHistory(): Boolean {
        return motionStorage.clearMotionHistory()
    }

    // Initialize sensors
    fun startDetection(callback: (List<String>) -> Unit) {
        motionCallback = callback
        baselineStepCount = -1  // Reset baseline
        lastDetectionTime = System.currentTimeMillis()

        // Set up accelerometer
        sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)?.let { accelerometer ->
            sensorManager.registerListener(
                this,
                accelerometer,
                SensorManager.SENSOR_DELAY_NORMAL
            )
        } ?: Log.w(TAG, "Linear acceleration sensor not available")

        // Set up step counter
        sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)?.let { stepSensor ->
            sensorManager.registerListener(
                this,
                stepSensor,
                SensorManager.SENSOR_DELAY_NORMAL
            )
        } ?: Log.w(TAG, "Step counter sensor not available")

        // Set up pressure sensor for altitude
        sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE)?.let { pressureSensor ->
            sensorManager.registerListener(
                this,
                pressureSensor,
                SensorManager.SENSOR_DELAY_NORMAL
            )
        } ?: Log.w(TAG, "Pressure sensor not available")

        // Set up location updates for speed
        try {
            locationManager.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                2000L, // Update every 2 seconds
                1f,
                locationListener
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "Location permission not granted", e)
        }
    }

    fun stopDetection() {
        sensorManager.unregisterListener(this)
        try {
            locationManager.removeUpdates(locationListener)
        } catch (e: SecurityException) {
            Log.e(TAG, "Location permission not granted", e)
        }
        motionCallback = null
        baselineStepCount = -1
    }

    // Main motion detection algorithm
    private fun detectMotion(
        sessionSteps: Int,
        acceleration: Double,
        altitudeChange: Double,
        speed: Double
    ): List<String> {
        val motions = mutableListOf<String>()

        Log.d(TAG, "Detection - Steps: $sessionSteps, Accel: $acceleration, Speed: $speed, Alt: $altitudeChange")

        // Check for stationary state (highest priority)
        // Very strict conditions: minimal steps, low acceleration, no altitude change, no speed
        if (sessionSteps <= STATIONARY_STEPS_THRESHOLD && 
            acceleration <= STATIONARY_ACCEL_THRESHOLD &&
            abs(altitudeChange) <= 0.5 && 
            speed <= STATIONARY_SPEED_THRESHOLD) {
            motions.add("stationary")
            return motions  // Return early if clearly stationary
        }

        // Check for vehicular motion first (high speed with low steps)
        // This takes priority over walking/jogging checks
        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD && 
            speed >= VEHICLE_SPEED_MIN) {
            motions.add("vehicle/subway/ferry/train")
            return motions
        }

        // Check for jogging/running (high step count AND high speed)
        if (sessionSteps >= JOGGING_STEPS_THRESHOLD && 
            speed >= JOGGING_SPEED_MIN && 
            speed <= JOGGING_SPEED_MAX) {
            motions.add("jogging/running")
            return motions
        }

        // Check for cycling (high speed with moderate steps)
        if (sessionSteps >= WALKING_STEPS_THRESHOLD && 
            speed >= CYCLING_SPEED_MIN && 
            speed < VEHICLE_SPEED_MIN) {
            motions.add("cycling")
            return motions
        }

        // Check for walking - now with multiple detection methods
        // Method 1: GPS speed based (outdoor walking)
        val isWalkingBySpeed = speed >= WALKING_SPEED_THRESHOLD && speed < JOGGING_SPEED_MIN
        // Method 2: Step count based (works better indoors where GPS may be inaccurate)
        val isWalkingBySteps = sessionSteps >= WALKING_STEPS_THRESHOLD
        // Method 3: Moderate steps with some acceleration (transitional walking)
        val isWalkingByAccel = sessionSteps >= LIMITED_MOTION_STEPS_THRESHOLD && acceleration > 0.5
        
        if (isWalkingBySteps || (isWalkingBySpeed && sessionSteps > STATIONARY_STEPS_THRESHOLD) || isWalkingByAccel) {
            motions.add("walking")
            return motions
        }

        // Check for elevator/escalator (significant altitude change with low steps)
        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD && 
            abs(altitudeChange) > 4.0 && 
            speed < JOGGING_SPEED_MIN) {
            motions.add("escalator/elevator")
            return motions
        }

        // Check for limited motion - some movement but not enough to classify as walking
        // Must have more than stationary thresholds but less than walking thresholds
        if (sessionSteps > STATIONARY_STEPS_THRESHOLD && sessionSteps < WALKING_STEPS_THRESHOLD) {
            motions.add("limited motion")
            return motions
        }
        
        // Very low activity that doesn't meet stationary criteria
        // (e.g., minor fidgeting, phone movement)
        if (acceleration > STATIONARY_ACCEL_THRESHOLD && sessionSteps <= STATIONARY_STEPS_THRESHOLD) {
            motions.add("limited motion")
            return motions
        }

        // Fallback: if we got here with some steps but no classification, use limited motion
        if (motions.isEmpty() && sessionSteps > 0) {
            motions.add("limited motion")
        }

        // Ultimate fallback for empty motions list
        if (motions.isEmpty()) {
            motions.add("stationary")
        }

        return motions
    }

    // Sensor event handling
    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_LINEAR_ACCELERATION -> {
                // Calculate magnitude of acceleration vector
                val x = event.values[0]
                val y = event.values[1]
                val z = event.values[2]
                lastAcceleration = sqrt((x * x + y * y + z * z).toDouble())
            }
            Sensor.TYPE_STEP_COUNTER -> {
                val totalSteps = event.values[0].toInt()
                
                // Initialize baseline on first reading
                if (baselineStepCount == -1) {
                    baselineStepCount = totalSteps
                    currentStepCount = 0
                    Log.d(TAG, "Baseline step count set to: $baselineStepCount")
                } else {
                    // Calculate steps since detection started
                    currentStepCount = totalSteps - baselineStepCount
                }
            }
            Sensor.TYPE_PRESSURE -> {
                // Only run detection at intervals to avoid spam
                val currentTime = System.currentTimeMillis()
                if (currentTime - lastDetectionTime < DETECTION_INTERVAL_MS) {
                    return
                }
                lastDetectionTime = currentTime

                // Convert pressure to altitude using barometric formula
                val pressure = event.values[0]
                val altitude = SensorManager.getAltitude(
                    SensorManager.PRESSURE_STANDARD_ATMOSPHERE,
                    pressure
                ).toDouble()
                val altitudeChange = if (lastAltitude != 0.0) {
                    altitude - lastAltitude
                } else {
                    0.0
                }
                lastAltitude = altitude

                // Detect motion with session-based step count
                val motions = detectMotion(
                    sessionSteps = currentStepCount,
                    acceleration = lastAcceleration,
                    altitudeChange = altitudeChange,
                    speed = currentSpeed
                )

                // Debug Update
                com.google.mediapipe.examples.llminference.data.DebugRepository.updateMotion(
                    accel = lastAcceleration,
                    steps = currentStepCount,
                    speed = currentSpeed,
                    alt = altitude,
                    clazz = motions.firstOrNull() ?: "Unknown"
                )

                // Save motion detection to storage
                motionStorage.saveMotionDetection(motions)

                // Notify callback with detected motions
                motionCallback?.invoke(motions)
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
        // Handle accuracy changes if needed
    }

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            val rawSpeed = location.speed.toDouble()
            // Simple low-pass filter to smooth out GPS noise
            // alpha = 0.7 means we keep 70% of history and take 30% of new value
            var smoothedSpeed = (currentSpeed * 0.7) + (rawSpeed * 0.3)
            
            // Dead zone: treat speeds below 0.4 m/s as 0 (GPS drift mitigation)
            if (smoothedSpeed < 0.4) {
                smoothedSpeed = 0.0
            }
            currentSpeed = smoothedSpeed
            Log.d(TAG, "Speed updated: $currentSpeed m/s (raw: $rawSpeed)")
        }

        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }
}
