package com.autolife.shared.analyzer

import kotlin.math.abs

/**
 * Pure motion classification algorithm.
 * Takes sensor readings and returns a list of detected motion types.
 * No platform dependencies — runs identically on Android and iOS.
 */
object MotionClassifier {
    private const val STATIONARY_STEPS_THRESHOLD = 2
    private const val LIMITED_MOTION_STEPS_THRESHOLD = 10
    private const val WALKING_STEPS_THRESHOLD = 50
    private const val JOGGING_STEPS_THRESHOLD = 140

    private const val STATIONARY_ACCEL_THRESHOLD = 0.1
    private const val STATIONARY_SPEED_THRESHOLD = 0.1
    private const val WALKING_SPEED_THRESHOLD = 1.8
    private const val JOGGING_SPEED_MIN = 2.0
    private const val JOGGING_SPEED_MAX = 5.0
    private const val CYCLING_SPEED_MIN = 4.0
    private const val VEHICLE_SPEED_MIN = 5.0

    fun classify(
        sessionSteps: Int,
        acceleration: Double,
        altitudeChange: Double,
        speed: Double
    ): List<String> {
        val motions = mutableListOf<String>()
        val absAltitudeDelta = abs(altitudeChange)

        if (sessionSteps <= STATIONARY_STEPS_THRESHOLD &&
            acceleration <= STATIONARY_ACCEL_THRESHOLD &&
            absAltitudeDelta <= 0.1 &&
            speed <= STATIONARY_SPEED_THRESHOLD
        ) {
            motions.add("stationary")
        }

        if (sessionSteps >= JOGGING_STEPS_THRESHOLD &&
            speed >= JOGGING_SPEED_MIN &&
            speed <= JOGGING_SPEED_MAX
        ) {
            motions.add("jogging/running")
        }

        if (sessionSteps >= WALKING_STEPS_THRESHOLD && speed < WALKING_SPEED_THRESHOLD) {
            motions.add("walking")
        }

        if (sessionSteps >= WALKING_STEPS_THRESHOLD && speed >= CYCLING_SPEED_MIN) {
            motions.add("cycling")
        }

        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD && speed > 2.0 || speed > VEHICLE_SPEED_MIN) {
            motions.add("vehicle/subway/ferry/train")
        }

        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD &&
            altitudeChange > 2.5 &&
            speed < 2.0
        ) {
            motions.add("escalator/elevator")
        }

        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD &&
            absAltitudeDelta <= 1.0 &&
            speed < 0.5
        ) {
            motions.add("limited motion")
        }

        if (motions.isEmpty() &&
            sessionSteps >= WALKING_STEPS_THRESHOLD &&
            speed in 0.5..<JOGGING_SPEED_MIN
        ) {
            motions.add("walking")
        }

        if (motions.isEmpty() && sessionSteps > STATIONARY_STEPS_THRESHOLD) {
            motions.add("limited motion")
        }

        if (motions.isEmpty()) {
            motions.add("stationary")
        }

        return motions.distinct()
    }
}
