import Foundation
import CoreLocation
import ComposeApp

class IOSLocationProvider: NSObject, LocationProvider, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<LocationData?, Never>?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
    }

    func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }

    func getCurrentLocation() async -> LocationData? {
        let status = manager.authorizationStatus
        guard status == .authorizedWhenInUse || status == .authorizedAlways else {
            requestPermission()
            return nil
        }

        return await withCheckedContinuation { continuation in
            // Resume any pending continuation to prevent leaks from concurrent calls
            self.continuation?.resume(returning: nil)
            self.continuation = continuation
            manager.requestLocation()
        }
    }

    // MARK: - CLLocationManagerDelegate

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else {
            continuation?.resume(returning: nil)
            continuation = nil
            return
        }
        let data = LocationData(
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            speed: max(0, location.speed),
            altitude: location.altitude
        )
        continuation?.resume(returning: data)
        continuation = nil
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        continuation?.resume(returning: nil)
        continuation = nil
    }
}
