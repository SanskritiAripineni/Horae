import Foundation
import CoreMotion
import ComposeApp

class IOSMotionSensorProvider: MotionSensorProvider {
    private let motionManager = CMMotionActivityManager()
    private let pedometer = CMPedometer()
    private let altimeter = CMAltimeter()
    private var isRunning = false
    private var motionHistory: [String] = []
    private var callback: (([String]) -> Void)?

    func startDetection(callback: @escaping ([String]) -> Void) {
        guard !isRunning else { return }
        isRunning = true
        self.callback = callback
        motionHistory = []

        // Motion activity detection
        if CMMotionActivityManager.isActivityAvailable() {
            motionManager.startActivityUpdates(to: .main) { [weak self] activity in
                guard let activity = activity, let self = self else { return }
                var types: [String] = []
                if activity.walking { types.append("Walking") }
                if activity.running { types.append("Running") }
                if activity.cycling { types.append("Cycling") }
                if activity.automotive { types.append("Driving") }
                if activity.stationary { types.append("Stationary") }
                if types.isEmpty { types.append("Unknown") }

                self.motionHistory.append(contentsOf: types)
                self.callback?(types)
            }
        }
    }

    func stopDetection() {
        guard isRunning else { return }
        isRunning = false
        motionManager.stopActivityUpdates()
        pedometer.stopUpdates()
        callback = nil
    }

    func getMotionHistory() -> String? {
        guard !motionHistory.isEmpty else { return nil }
        // Summarize motion history
        var counts: [String: Int] = [:]
        for m in motionHistory {
            counts[m, default: 0] += 1
        }
        let summary = counts.sorted { $0.value > $1.value }
            .map { "\($0.key): \($0.value)" }
            .joined(separator: ", ")
        return summary
    }

    func clearMotionHistory() -> Bool {
        motionHistory.removeAll()
        return true
    }
}
