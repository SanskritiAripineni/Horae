package com.autolife.shared.analyzer

import kotlin.math.abs

/**
 * Pure motion classification algorithm.
 * Takes sensor readings and returns a list of detected motion types.
 * No platform dependencies — runs identically on Android and iOS.
 */
object MotionClassifier {

    // Thresholds for session-based step counting
    private const val STATIONARY_STEPS_THRESHOLD = 5
    private const val LIMITED_MOTION_STEPS_THRESHOLD = 15
    private const val WALKING_STEPS_THRESHOLD = 30
    private const val JOGGING_STEPS_THRESHOLD = 80

    private const val STATIONARY_ACCEL_THRESHOLD = 0.8
    private const val STATIONARY_SPEED_THRESHOLD = 0.5  // m/s
    private const val WALKING_SPEED_THRESHOLD = 0.5      // m/s (~1.8 km/h)
    private const val JOGGING_SPEED_MIN = 2.0            // m/s
    private const val JOGGING_SPEED_MAX = 5.0            // m/s
    private const val CYCLING_SPEED_MIN = 4.0            // m/s
    private const val VEHICLE_SPEED_MIN = 5.0            // m/s (~18 km/h)

    fun classify(
        sessionSteps: Int,
        acceleration: Double,
        altitudeChange: Double,
        speed: Double
    ): List<String> {
        val motions = mutableListOf<String>()

        // Stationary (highest priority)
        if (sessionSteps <= STATIONARY_STEPS_THRESHOLD &&
            acceleration <= STATIONARY_ACCEL_THRESHOLD &&
            abs(altitudeChange) <= 0.5 &&
            speed <= STATIONARY_SPEED_THRESHOLD
        ) {
            motions.add("stationary")
            return motions
        }

        // Vehicular motion (high speed with low steps)
        if (sessionSteps <= LIMITED_MOTION_STEPS_THRESHOLD &&
            speed >= VEHICLE_SPEED_MIN
        ) {
            motions.add("vehicle/subway/ferry/train")
            return motions
        }

        // Jogging/running (high step count AND high speed)
        if (sessionSteps >= JOGGING_STEPS_THRESHOLD &&
            speed >= JOGGING_SPEED_MIN &&
            speed <= JOGGING_SPEED_MAX
        ) {
            motions.add("jogging/running")
            return motions
        }

        // Cycling (high speed with moderate steps)
        if (sessionSteps >= WALKING_STEPS_THRESHOLD &&
            speed >= CYCLING_SPEED_MIN &&
            speed < VEHICLE_SPEED_MIN
        ) {
            motions.add("cycling")
            return motions
        }

        // Walking — multiple detection methods
        val isWalkingBySpeed = speed >= WALKING_SPEED_THRESHOLD && speed < JOGGING_SPEED_MIN
        val isWalkingBySteps = sessionSteps >= WALKING_STEPS_THRESHOLD
        val isWalkingByAccel = sessionSteps >= LIMITED_MOTION_STEPS_THRESHOLD && acceleration > 0.5

        if (isWalkingBySteps || (isWalkingBySpeed && sessionSteps > STATIONARY_STEPS_THRESHOLD) || isWalkingByAccel) {
            motions.add("walking")
            return motions
        }

        // Elevator/escalator (altitude change with very few steps)
        if (sessionSteps <= 3 &&
            abs(altitudeChange) > 6.0 &&
            speed < WALKING_SPEED_THRESHOLD &&
            acceleration < 0.5
        ) {
            motions.add("escalator/elevator")
            return motions
        }

        // Limited motion — some movement but not enough for walking
        if (sessionSteps > STATIONARY_STEPS_THRESHOLD && sessionSteps < WALKING_STEPS_THRESHOLD) {
            motions.add("limited motion")
            return motions
        }

        // Minor fidgeting / phone movement
        if (acceleration > STATIONARY_ACCEL_THRESHOLD && sessionSteps <= STATIONARY_STEPS_THRESHOLD) {
            motions.add("limited motion")
            return motions
        }

        // Fallback
        if (motions.isEmpty() && sessionSteps > 0) {
            motions.add("limited motion")
        }
        if (motions.isEmpty()) {
            motions.add("stationary")
        }

        return motions
    }
}
