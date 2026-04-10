import Foundation
import MapKit
import ComposeApp

class IOSMapImageFetcher: MapImageFetcher {

    func fetchMapImage(latitude: Double, longitude: Double) async throws -> KotlinByteArray? {
        let options = MKMapSnapshotter.Options()
        options.region = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: latitude, longitude: longitude),
            latitudinalMeters: 500,
            longitudinalMeters: 500
        )
        options.size = CGSize(width: 600, height: 400)
        options.mapType = .standard

        let snapshotter = MKMapSnapshotter(options: options)

        do {
            let snapshot = try await snapshotter.start()
            guard let pngData = snapshot.image.pngData() else { return nil }
            return pngData.toKotlinByteArray()
        } catch {
            return nil
        }
    }
}

extension Data {
    func toKotlinByteArray() -> KotlinByteArray {
        let nsData = self as NSData
        let kotlinArray = KotlinByteArray(size: Int32(nsData.length))
        let bytes = nsData.bytes.assumingMemoryBound(to: Int8.self)
        for i in 0..<nsData.length {
            kotlinArray.set(index: Int32(i), value: bytes[i])
        }
        return kotlinArray
    }
}
