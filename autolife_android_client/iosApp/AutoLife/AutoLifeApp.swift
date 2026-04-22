import SwiftUI
import ComposeApp
import UIKit
import Foundation

@main
struct AutoLifeApp: App {

    init() {
        // Initialize shared KMP singletons (types re-exported via ComposeApp framework)
        let backendUrl = Bundle.main.object(forInfoDictionaryKey: "BACKEND_URL") as? String
            ?? "http://localhost:8000"
        AutoLifeApi.shared.doInit(baseUrl: backendUrl)

        let geminiKey = Bundle.main.object(forInfoDictionaryKey: "GEMINI_API_KEY") as? String ?? ""
        AiClientProvider.shared.doInit(client: GeminiAiClient(apiKey: geminiKey))

        let driver = DriverFactory_iosKt.createNativeDriver()
        DatabaseRepository.shared.doInit(driver: driver)

        // Wire up PlatformStateProvider callbacks (mirrors Android AutoLifeApp.bridgeDebugToPlatformState)
        setupPlatformCallbacks()
    }

    var body: some Scene {
        WindowGroup {
            ComposeView()
                .ignoresSafeArea(.keyboard)
        }
    }

    private func setupPlatformCallbacks() {
        let wifiProvider = IOSWifiNetworkProvider()

        // Service toggle: Kotlin iosMain -> IOSServiceBridge -> Swift
        IOSServiceBridge.shared.onServiceToggle = { shouldStart in
            Task { @MainActor in
                if shouldStart.boolValue {
                    IOSSensorServiceManager.shared.start()
                } else {
                    IOSSensorServiceManager.shared.stop()
                }
            }
        }

        // Demo mode toggle from DevDashboard
        PlatformStateProvider.shared.onDemoModeChanged = { enabled in
            Task { @MainActor in
                IOSSensorServiceManager.shared.setDemoMode(enabled: enabled.boolValue)
            }
        }

        // Permanent motion toggle from DevDashboard
        PlatformStateProvider.shared.onPermanentMotionChanged = { enabled in
            Task { @MainActor in
                IOSSensorServiceManager.shared.setPermanentMotion(enabled: enabled.boolValue)
            }
        }

        // Export journals from DevDashboard
        PlatformStateProvider.shared.onExportRequested = {
            IOSDataExporter.exportJournals()
        }

        // Generate journal now from DevDashboard
        PlatformStateProvider.shared.onGenerateJournalRequested = {
            Task { @MainActor in
                IOSSensorServiceManager.shared.generateJournalNow()
            }
        }

        PlatformStateProvider.shared.onServiceToggleRequested = { shouldStart in
            Task { @MainActor in
                if shouldStart.boolValue {
                    IOSSensorServiceManager.shared.start()
                } else {
                    IOSSensorServiceManager.shared.stop()
                }
            }
        }

        PlatformStateProvider.shared.onBatteryLevelRequested = {
            UIDevice.current.isBatteryMonitoringEnabled = true
            let level = UIDevice.current.batteryLevel
            if level < 0 { return nil }
            return KotlinInt(int: Int32(level * 100))
        }
        PlatformStateProvider.shared.onBatteryDeviceInfoRequested = {
            UIDevice.current.isBatteryMonitoringEnabled = true
            let model = "\(UIDevice.current.systemName) device (\(UIDevice.current.model))"
            return BatteryDeviceInfo(
                platform: "iOS",
                deviceModel: model,
                osVersion: "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)",
                appVersion: currentAppVersion()
            )
        }
        PlatformStateProvider.shared.onBatteryEnvironmentRequested = {
            let networks = wifiProvider.getVisibleNetworks().joined(separator: ", ")
            return BatteryRunEnvironment(
                screenIntent: BatteryScreenIntent.mostlyScreenOff,
                appStateIntent: BatteryAppStateIntent.mostlyBackground,
                networkSummary: networks.isEmpty ? "Network state unavailable" : networks,
                lowPowerModeEnabled: KotlinBoolean(bool: ProcessInfo.processInfo.isLowPowerModeEnabled)
            )
        }

        PlatformStateProvider.shared.onBatteryAssessmentExportRequested = { report in
            IOSDataExporter.exportBatteryReport(content: report)
        }

        PlatformStateProvider.shared.setPlatformName(name: "iOS")
        PlatformStateProvider.shared.loadBatteryAssessments()
        PlatformStateProvider.shared.refreshBatteryLevel()
    }

    private func currentAppVersion() -> String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
        return "\(version) (\(build))"
    }
}

struct ComposeView: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> UIViewController {
        MainViewControllerKt.MainViewController()
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
}
