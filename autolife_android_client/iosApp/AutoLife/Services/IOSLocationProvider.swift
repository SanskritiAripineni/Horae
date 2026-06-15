import Foundation
import CoreLocation
import ComposeApp

class IOSLocationProvider: NSObject, LocationProvider, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private let geocoder = CLGeocoder()
    private var continuation: CheckedContinuation<LocationData?, Never>?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.pausesLocationUpdatesAutomatically = false
    }

    func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }

    func hasLocationAuthorization() -> Bool {
        let status = manager.authorizationStatus
        return status == .authorizedWhenInUse || status == .authorizedAlways
    }

    func getCurrentLocation() async -> LocationData? {
        let status = manager.authorizationStatus
        guard status == .authorizedWhenInUse || status == .authorizedAlways else {
            requestPermission()
            return nil
        }
        manager.allowsBackgroundLocationUpdates = false

        return await withCheckedContinuation { continuation in
            // Resume any pending continuation to prevent leaks from concurrent calls
            self.continuation?.resume(returning: nil)
            self.continuation = continuation
            manager.requestLocation()
        }
    }

    func reverseGeocode(location: LocationData) async -> String? {
        let clLocation = CLLocation(latitude: location.latitude, longitude: location.longitude)

        do {
            let placemarks = try await geocoder.reverseGeocodeLocation(clLocation)
            guard let placemark = placemarks.first else { return nil }

            let parts: [String] = [
                placemark.name,
                placemark.subLocality,
                placemark.locality,
                placemark.administrativeArea,
                placemark.country
            ].compactMap { value in
                guard let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines),
                      !trimmed.isEmpty else { return nil }
                return trimmed
            }

            let uniqueParts = Array(NSOrderedSet(array: parts)) as? [String] ?? parts
            return uniqueParts.isEmpty ? nil : uniqueParts.joined(separator: ", ")
        } catch {
            return nil
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
