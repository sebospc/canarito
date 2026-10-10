import CanaritoCore
import CoreLocation

/// Significant-change plus one region around the last reading: the region wakes the app sooner than a
/// significant change does when the person drives out of town. Neither is relied on after a
/// force-quit; the server keeps the last position, so a missed wake only leaves it stale.
@MainActor
final class LocationService: NSObject, CLLocationManagerDelegate {
    var onFix: (Fix) -> Void = { _ in }
    var onAccess: (LocationAccess) -> Void = { _ in }

    private let manager = CLLocationManager()
    /// Background use only holds while a session is alive. Recreated on every launch.
    private var session: CLServiceSession?
    private static let askedAlwaysKey = "asked-location-always"
    /// A bit over the 1 km the server keeps: leaving it means the rounded position probably changed.
    private static let regionRadius: CLLocationDistance = 1500
    private static let regionIdentifier = "last-fix"

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
    }

    var access: LocationAccess {
        switch manager.authorizationStatus {
        case .notDetermined: .notDetermined
        case .denied, .restricted: .denied
        case .authorizedWhenInUse: .whileUsing
        case .authorizedAlways: .always
        @unknown default: .denied
        }
    }

    func start() {
        switch access {
        case .always:
            session = CLServiceSession(authorization: .always)
            manager.startMonitoringSignificantLocationChanges()
        case .whileUsing:
            session = CLServiceSession(authorization: .whenInUse)
            manager.startMonitoringSignificantLocationChanges()
        case .notDetermined, .denied:
            break
        }
        onAccess(access)
    }

    func stop() {
        manager.stopMonitoringSignificantLocationChanges()
        manager.monitoredRegions.forEach(manager.stopMonitoring(for:))
        session = nil
    }

    func requestWhenInUse() {
        if access == .notDetermined { manager.requestWhenInUseAuthorization() }
    }

    /// Once: iOS then offers "Always" with our purpose string.
    func requestAlwaysOnce() {
        guard access == .whileUsing, !UserDefaults.standard.bool(forKey: Self.askedAlwaysKey) else { return }
        UserDefaults.standard.set(true, forKey: Self.askedAlwaysKey)
        manager.requestAlwaysAuthorization()
    }

    /// On app open, one fresh reading instead of trusting an old one.
    func requestFreshFix() {
        if access == .always || access == .whileUsing { manager.requestLocation() }
    }

    private func watch(around location: CLLocation) {
        guard CLLocationManager.isMonitoringAvailable(for: CLCircularRegion.self), access == .always else { return }
        manager.monitoredRegions.forEach(manager.stopMonitoring(for:))
        manager.startMonitoring(for: CLCircularRegion(center: location.coordinate, radius: Self.regionRadius, identifier: Self.regionIdentifier))
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let newest = locations.last else { return }
        MainActor.assumeIsolated {
            watch(around: newest)
            onFix(Fix(lat: newest.coordinate.latitude, lon: newest.coordinate.longitude, timestamp: newest.timestamp))
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didExitRegion region: CLRegion) {
        MainActor.assumeIsolated { requestFreshFix() }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        // A failed reading changes nothing: the server keeps the last position it has.
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        MainActor.assumeIsolated {
            start()
            requestFreshFix()
        }
    }
}
