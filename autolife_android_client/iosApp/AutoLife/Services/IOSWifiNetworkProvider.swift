import Foundation
import NetworkExtension
import SystemConfiguration.CaptiveNetwork
import ComposeApp

class IOSWifiNetworkProvider: WifiNetworkProvider {

    func getVisibleNetworks() -> [String] {
        // iOS is more restrictive than Android for WiFi scanning.
        // We can only get the currently connected SSID, not scan for visible networks.
        // Requires com.apple.developer.networking.wifi-info entitlement.
        var ssids: [String] = []

        if let interfaces = CNCopySupportedInterfaces() as? [String] {
            for interface in interfaces {
                if let info = CNCopyCurrentNetworkInfo(interface as CFString) as? [String: Any],
                   let ssid = info[kCNNetworkInfoKeySSID as String] as? String {
                    ssids.append(ssid)
                }
            }
        }

        return ssids.isEmpty ? ["(No WiFi info available)"] : ssids
    }
}
