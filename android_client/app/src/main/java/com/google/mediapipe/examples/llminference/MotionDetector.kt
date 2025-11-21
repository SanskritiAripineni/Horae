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
    private val DETECTION_INTERVAL_MS = 2000L  // Only detect every 2 seconds

    private var motionCallback: ((List<String>) -> Unit)? = null

    companion object {
        private const val TAG = "MotionDetector"
        // Adjusted thresholds for session-based step counting
        private const val STATIONARY_STEPS_THRESHOLD = 5
        private const val LIMITED_MOTION_STEPS_THRESHOLD = 15
        private const val WALKING_STEPS_THRESHOLD = 30
        private const val JOGGING_STEPS_THRESHOLD = 80
        
        private const val STATIONARY_ACCEL_THRESHOLD = 0.5
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
        if (sessionSteps <= STATIONARY_STEPS_THRESHOLD && 
            acceleration <= STATIONARY_ACCEL_THRESHOLD &&
            abs(altitudeChange) <= 0.5 && 
            speed <= 0.2) {
            motions.add("stationary")
            return motions  // Return early if clearly stationary
        }

        // Check for limited motion
        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD && 
            abs(altitudeChange) <= 1.0 && 
            speed < WALKING_SPEED_THRESHOLD) {
            motions.add("limited motion")
        }

        // Check for walking
        if (sessionSteps >= WALKING_STEPS_THRESHOLD && 
            speed >= WALKING_SPEED_THRESHOLD && 
            speed < JOGGING_SPEED_MIN) {
            motions.add("walking")
        }

        // Check for jogging/running
        if (sessionSteps >= JOGGING_STEPS_THRESHOLD && 
            speed >= JOGGING_SPEED_MIN && 
            speed <= JOGGING_SPEED_MAX) {
            motions.add("jogging/running")
        }

        // Check for cycling (high speed with moderate steps)
        if (sessionSteps >= WALKING_STEPS_THRESHOLD && 
            speed >= CYCLING_SPEED_MIN && 
            speed < VEHICLE_SPEED_MIN) {
            motions.add("cycling")
        }

        // Check for vehicular motion (high speed with low steps)
        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD && 
            speed >= VEHICLE_SPEED_MIN) {
            motions.add("vehicle/subway/ferry/train")
        }

        // Check for elevator/escalator
        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD && 
            abs(altitudeChange) > 2.5 && 
            speed < JOGGING_SPEED_MIN) {
            motions.add("escalator/elevator")
        }

        // If no motions detected but there's some activity, default to limited motion
        if (motions.isEmpty() && (sessionSteps > 0 || acceleration > 0.1)) {
            motions.add("limited motion")
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
            currentSpeed = location.speed.toDouble() // Speed in meters/second
            Log.d(TAG, "Speed updated: $currentSpeed m/s")
        }

        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }
}
