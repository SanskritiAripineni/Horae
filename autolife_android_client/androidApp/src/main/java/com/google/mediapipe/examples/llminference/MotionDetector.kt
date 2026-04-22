package com.google.mediapipe.examples.llminference

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.util.Log
import com.autolife.shared.analyzer.MotionClassifier
import com.autolife.shared.model.WindowFeatures
import com.autolife.shared.platform.MotionSensorProvider
import kotlinx.coroutines.delay
import kotlin.math.sqrt

class MotionDetector(private val context: Context) : SensorEventListener, MotionSensorProvider {
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val motionStorage = MotionStorage(context)

    private var motionCallback: ((List<String>) -> Unit)? = null
    private var activeConsumers = 0
    private var currentStepCounter = -1
    private var currentAltitude: Double? = null
    private var lastAccelerationMagnitude = 0.0
    private var accelSum = 0.0
    private var accelSamples = 0L
    private var lastDetectionTime = 0L

    companion object {
        private const val TAG = "MotionDetector"
        private const val DETECTION_INTERVAL_MS = 2000L
    }

    override fun getMotionHistory(): String? = motionStorage.getMotionHistory()

    override fun clearMotionHistory(): Boolean = motionStorage.clearMotionHistory()

    override fun startDetection(callback: (List<String>) -> Unit) {
        motionCallback = callback
        acquireSensors()
    }

    override fun stopDetection() {
        motionCallback = null
        releaseSensors()
    }

    suspend fun collectWindowFeatures(
        windowDurationMs: Long,
        speedMps: Double?,
        ssidFingerprint: String,
        motionPolicy: MotionCollectionPolicy? = null,
        onClassified: ((List<String>) -> Unit)? = null
    ): WindowFeatures {
        acquireSensors()
        try {
            val windowStartMs = System.currentTimeMillis()
            val startStep = currentStepCounter
            val startAccelSum = accelSum
            val startAccelSamples = accelSamples
            val startAltitude = currentAltitude

            waitForWindowCompletion(
                windowDurationMs = windowDurationMs,
                speedMps = speedMps,
                motionPolicy = motionPolicy,
                startStep = startStep,
                startAccelSum = startAccelSum,
                startAccelSamples = startAccelSamples,
                startAltitude = startAltitude
            )

            val windowFeatures = buildWindowFeatures(
                windowStartMs = windowStartMs,
                windowEndMs = System.currentTimeMillis(),
                speedMps = speedMps,
                ssidFingerprint = ssidFingerprint,
                startStep = startStep,
                startAccelSum = startAccelSum,
                startAccelSamples = startAccelSamples,
                startAltitude = startAltitude
            )

            val motions = MotionClassifier.classify(
                sessionSteps = windowFeatures.stepCount,
                acceleration = windowFeatures.avgAcceleration,
                altitudeChange = windowFeatures.altitudeDelta,
                speed = speedMps ?: 0.0
            )
            motionStorage.saveMotionDetection(motions)
            onClassified?.invoke(motions)

            return windowFeatures
        } finally {
            releaseSensors()
        }
    }

    private suspend fun waitForWindowCompletion(
        windowDurationMs: Long,
        speedMps: Double?,
        motionPolicy: MotionCollectionPolicy?,
        startStep: Int,
        startAccelSum: Double,
        startAccelSamples: Long,
        startAltitude: Double?
    ) {
        if (motionPolicy == null) {
            delay(windowDurationMs)
            return
        }

        var elapsedMs = 0L
        while (elapsedMs < windowDurationMs) {
            val sleepMs = minOf(motionPolicy.checkIntervalMs, windowDurationMs - elapsedMs)
            delay(sleepMs)
            elapsedMs += sleepMs

            if (elapsedMs < motionPolicy.minDurationMs) {
                continue
            }

            if (isStableStationaryWindow(
                    speedMps = speedMps,
                    motionPolicy = motionPolicy,
                    startStep = startStep,
                    startAccelSum = startAccelSum,
                    startAccelSamples = startAccelSamples,
                    startAltitude = startAltitude
                )
            ) {
                return
            }
        }
    }

    private fun isStableStationaryWindow(
        speedMps: Double?,
        motionPolicy: MotionCollectionPolicy,
        startStep: Int,
        startAccelSum: Double,
        startAccelSamples: Long,
        startAltitude: Double?
    ): Boolean {
        val stepCount = currentStepCountSince(startStep)
        val avgAcceleration = averageAccelerationSince(startAccelSum, startAccelSamples)
        val altitudeDelta = altitudeDeltaSince(startAltitude)
        val effectiveSpeed = speedMps ?: 0.0

        return stepCount <= motionPolicy.maxStepDelta &&
            avgAcceleration <= motionPolicy.maxAvgAcceleration &&
            kotlin.math.abs(altitudeDelta) <= motionPolicy.maxAltitudeDeltaM &&
            effectiveSpeed <= motionPolicy.maxSpeedMps
    }

    private fun buildWindowFeatures(
        windowStartMs: Long,
        windowEndMs: Long,
        speedMps: Double?,
        ssidFingerprint: String,
        startStep: Int,
        startAccelSum: Double,
        startAccelSamples: Long,
        startAltitude: Double?
    ): WindowFeatures {
        return WindowFeatures(
            windowStartMs = windowStartMs,
            windowEndMs = windowEndMs,
            stepCount = currentStepCountSince(startStep),
            avgAcceleration = averageAccelerationSince(startAccelSum, startAccelSamples),
            altitudeDelta = altitudeDeltaSince(startAltitude),
            speedMps = speedMps,
            ssidFingerprint = ssidFingerprint
        )
    }

    private fun currentStepCountSince(startStep: Int): Int =
        if (startStep >= 0 && currentStepCounter >= startStep) {
            currentStepCounter - startStep
        } else {
            0
        }

    private fun averageAccelerationSince(startAccelSum: Double, startAccelSamples: Long): Double {
        val accelDelta = accelSum - startAccelSum
        val accelSampleDelta = (accelSamples - startAccelSamples).coerceAtLeast(0)
        return if (accelSampleDelta > 0) accelDelta / accelSampleDelta else lastAccelerationMagnitude
    }

    private fun altitudeDeltaSince(startAltitude: Double?): Double =
        (currentAltitude ?: startAltitude ?: 0.0) - (startAltitude ?: currentAltitude ?: 0.0)

    fun snapshotWindowFeatures(
        windowStartMs: Long,
        windowEndMs: Long,
        speedMps: Double?,
        ssidFingerprint: String
    ): WindowFeatures {
        return WindowFeatures(
            windowStartMs = windowStartMs,
            windowEndMs = windowEndMs,
            stepCount = 0,
            avgAcceleration = lastAccelerationMagnitude,
            altitudeDelta = 0.0,
            speedMps = speedMps,
            ssidFingerprint = ssidFingerprint
        )
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_LINEAR_ACCELERATION -> {
                val x = event.values[0]
                val y = event.values[1]
                val z = event.values[2]
                lastAccelerationMagnitude = sqrt((x * x + y * y + z * z).toDouble())
                accelSum += lastAccelerationMagnitude
                accelSamples += 1
            }
            Sensor.TYPE_STEP_COUNTER -> {
                currentStepCounter = event.values[0].toInt()
            }
            Sensor.TYPE_PRESSURE -> {
                currentAltitude = SensorManager.getAltitude(
                    SensorManager.PRESSURE_STANDARD_ATMOSPHERE,
                    event.values[0]
                ).toDouble()
                maybeEmitDebugClassification()
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    private fun maybeEmitDebugClassification() {
        val callback = motionCallback ?: return
        val now = System.currentTimeMillis()
        if (now - lastDetectionTime < DETECTION_INTERVAL_MS) return
        lastDetectionTime = now

        val motions = MotionClassifier.classify(
            sessionSteps = 0,
            acceleration = lastAccelerationMagnitude,
            altitudeChange = 0.0,
            speed = 0.0
        )

        com.google.mediapipe.examples.llminference.data.DebugRepository.updateMotion(
            accel = lastAccelerationMagnitude,
            steps = 0,
            speed = 0.0,
            alt = currentAltitude ?: 0.0,
            clazz = motions.firstOrNull() ?: "Unknown"
        )
        motionStorage.saveMotionDetection(motions)
        callback.invoke(motions)
    }

    private fun acquireSensors() {
        activeConsumers += 1
        if (activeConsumers > 1) return

        sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        } ?: Log.w(TAG, "Linear acceleration sensor not available")

        sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        } ?: Log.w(TAG, "Step counter sensor not available")

        sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE)?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        } ?: Log.w(TAG, "Pressure sensor not available")
    }

    private fun releaseSensors() {
        activeConsumers = (activeConsumers - 1).coerceAtLeast(0)
        if (activeConsumers > 0) return
        sensorManager.unregisterListener(this)
    }
}
