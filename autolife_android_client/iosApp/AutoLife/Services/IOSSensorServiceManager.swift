import Foundation
import ComposeApp

/// iOS equivalent of Android's AutoLifeService.
/// Uses Timer-based polling to collect sensor data, feed PlatformStateProvider,
/// and generate journals — mirroring the Android foreground service behaviour.
@MainActor
class IOSSensorServiceManager {
    static let shared = IOSSensorServiceManager()

    private let locationProvider = IOSLocationProvider()
    private let motionProvider = IOSMotionSensorProvider()
    private let wifiProvider = IOSWifiNetworkProvider()
    private var pollTimer: Timer?
    private(set) var isRunning = false
    private var isDemoMode = false
    private var isPermanentMotionEnabled = false
    private var lastJournalTime: Int64 = 0
    private var lastLocationContext: String?
    private var currentMotionClass: String = "Idle"

    // Intervals matching Android AutoLifeService
    private let LOG_INTERVAL: TimeInterval = 60           // 1 minute
    private let JOURNAL_INTERVAL: Int64 = 30 * 60_000     // 30 minutes in ms
    private let DEMO_JOURNAL_INTERVAL: Int64 = 2 * 60_000 // 2 minutes in ms

    private init() {}

    // MARK: - Lifecycle

    func start() {
        guard !isRunning else { return }
        isRunning = true

        locationProvider.requestPermission()

        // Start motion detection
        motionProvider.startDetection { [weak self] types in
            guard let self = self else { return }
            let label = types.joined(separator: ", ")
            self.currentMotionClass = types.first ?? "Unknown"
            PlatformStateProvider.shared.updateMotion(
                acceleration: 0.0,
                stepCount: 0,
                speed: 0.0,
                altitude: 0.0,
                detectedClass: label.isEmpty ? "Idle" : label
            )

            // Insert motion log
            let now = Int64(Date().timeIntervalSince1970 * 1000)
            DatabaseRepository.shared.insertLog(log: SensorLog(
                id: 0,
                timestamp: now,
                type: "MOTION",
                content: label
            ))
        }

        PlatformStateProvider.shared.updateServiceState(isRunning: true, isDemoMode: isDemoMode)

        // Start polling timer
        pollTimer = Timer.scheduledTimer(withTimeInterval: LOG_INTERVAL, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.runPollCycle()
            }
        }

        // Run first poll immediately
        Task { await runPollCycle() }
    }

    func stop() {
        guard isRunning else { return }
        isRunning = false

        motionProvider.stopDetection()
        pollTimer?.invalidate()
        pollTimer = nil
        currentMotionClass = "Idle"

        PlatformStateProvider.shared.updateServiceState(isRunning: false, isDemoMode: isDemoMode)
        PlatformStateProvider.shared.updateMotion(
            acceleration: 0.0,
            stepCount: 0,
            speed: 0.0,
            altitude: 0.0,
            detectedClass: "Idle"
        )
    }

    func setDemoMode(enabled: Bool) {
        isDemoMode = enabled
        PlatformStateProvider.shared.updateServiceState(isRunning: isRunning, isDemoMode: isDemoMode)
    }

    func setPermanentMotion(enabled: Bool) {
        isPermanentMotionEnabled = enabled
        PlatformStateProvider.shared.updatePermanentMotion(enabled: enabled)
    }

    // MARK: - Poll cycle (mirrors Android's startLoop + startAnalysisCycle)

    private func runPollCycle() async {
        let now = Int64(Date().timeIntervalSince1970 * 1000)

        // 1. Location
        var speed: Double = 0
        var altitude: Double = 0
        if let loc = await locationProvider.getCurrentLocation() {
            speed = loc.speed
            altitude = loc.altitude

            PlatformStateProvider.shared.updateMotion(
                acceleration: 0.0,
                stepCount: 0,
                speed: speed,
                altitude: altitude,
                detectedClass: currentMotionClass
            )

            let content = String(format: "lat=%.6f lon=%.6f spd=%.1f alt=%.0f",
                                 loc.latitude, loc.longitude, speed, altitude)
            DatabaseRepository.shared.insertLog(log: SensorLog(
                id: 0,
                timestamp: now,
                type: "LOCATION",
                content: content
            ))

            let ssids = wifiProvider.getVisibleNetworks()
            let geocoderContext = await locationProvider.reverseGeocode(location: loc)

            // 2. Fuse geocoder + SSID context
            do {
                let ssidContext: String?
                if ssids.isEmpty || ssids == ["(No WiFi info available)"] {
                    ssidContext = nil
                } else {
                    let ssidPrompt = PromptBuilder.shared.buildWifiLocationPrompt(ssids: ssids)
                    let candidate = try await AiClientProvider.shared.client.generate(prompt: ssidPrompt)
                    let normalized = candidate.trimmingCharacters(in: .whitespacesAndNewlines)
                    ssidContext = normalized.lowercased().contains("ssid context unavailable") ? nil : normalized
                }

                let locationContext: String
                let inferenceSource: String
                if let geocoderContext, let ssidContext {
                    let fusionPrompt = PromptBuilder.shared.buildLocationFusionPrompt(
                        mapContext: geocoderContext,
                        osmContext: nil,
                        ssidContext: ssidContext
                    )
                    locationContext = try await AiClientProvider.shared.client.generate(prompt: fusionPrompt)
                    inferenceSource = "Fused geocoder + Wi-Fi"
                } else {
                    locationContext = geocoderContext ?? ssidContext ?? "Location unavailable"
                    inferenceSource = geocoderContext != nil ? "Reverse geocoder" : "Wi-Fi"
                }

                lastLocationContext = locationContext
                PlatformStateProvider.shared.updateLocation(
                    latitude: loc.latitude,
                    longitude: loc.longitude,
                    ssids: ssids,
                    inference: locationContext,
                    mapPreviewBytes: nil,
                    geocoderContext: geocoderContext,
                    osmContext: nil,
                    wifiContext: ssidContext,
                    inferenceSource: inferenceSource
                )

                DatabaseRepository.shared.insertLog(log: SensorLog(
                    id: 0,
                    timestamp: now,
                    type: "FUSION",
                    content: locationContext
                ))

                PlatformStateProvider.shared.updateLocationInference(inference: locationContext)
            } catch {
                // Non-fatal: AI calls may fail, continue polling
                PlatformStateProvider.shared.updateLocation(
                    latitude: loc.latitude,
                    longitude: loc.longitude,
                    ssids: ssids,
                    inference: geocoderContext ?? "Analysis unavailable: \(error.localizedDescription)",
                    mapPreviewBytes: nil,
                    geocoderContext: geocoderContext,
                    osmContext: nil,
                    wifiContext: nil,
                    inferenceSource: geocoderContext != nil ? "Reverse geocoder" : "Unavailable"
                )
            }
        }

        // 4. WiFi (standalone log)
        let networks = wifiProvider.getVisibleNetworks()
        if let ssid = networks.first, ssid != "(No WiFi info available)" {
            PlatformStateProvider.shared.updateLocationSsids(ssids: networks)
            DatabaseRepository.shared.insertLog(log: SensorLog(
                id: 0,
                timestamp: now,
                type: "WIFI",
                content: networks.joined(separator: ", ")
            ))
        }

        // 5. Journal generation check
        let journalInterval = isDemoMode ? DEMO_JOURNAL_INTERVAL : JOURNAL_INTERVAL
        if now - lastJournalTime >= journalInterval {
            await tryGenerateJournal(endTime: now, periodDurationMs: journalInterval)
            lastJournalTime = now
        }
    }

    // MARK: - Journal generation (mirrors Android JournalGenerator)

    func generateJournalNow() {
        Task {
            let now = Int64(Date().timeIntervalSince1970 * 1000)
            await tryGenerateJournal(endTime: now, periodDurationMs: DEMO_JOURNAL_INTERVAL)
        }
    }

    private func tryGenerateJournal(endTime: Int64, periodDurationMs: Int64) async {
        let startTime = endTime - periodDurationMs
        let logs = DatabaseRepository.shared.getLogsBetween(start: startTime, end: endTime)

        guard !logs.isEmpty else { return }

        // Format logs like Android JournalGenerator
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "HH:mm"

        let formattedLogs = logs.map { log in
            let date = Date(timeIntervalSince1970: Double(log.timestamp) / 1000.0)
            let time = dateFormatter.string(from: date)
            return "[\(time)] (\(log.type)): \(log.content)"
        }.joined(separator: "\n")

        let prompt = PromptBuilder.shared.buildJournalPrompt(refinedSegments: formattedLogs)

        do {
            let journalContent = try await AiClientProvider.shared.client.generate(prompt: prompt)

            PlatformStateProvider.shared.updateLastJournal(journal: journalContent)

            DatabaseRepository.shared.insertJournal(journal: JournalEntry(
                id: 0,
                createdTimestamp: endTime,
                periodStart: startTime,
                periodEnd: endTime,
                content: journalContent
            ))
        } catch {
            // Non-fatal: journal generation may fail, will retry next cycle
        }
    }
}
