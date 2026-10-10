import Foundation

/// A reading from the phone. Never leaves the phone as it is: `PositionPolicy.rounded` first.
public struct Fix: Equatable, Sendable {
    public let lat: Double
    public let lon: Double
    public let timestamp: Date

    public init(lat: Double, lon: Double, timestamp: Date) {
        self.lat = lat
        self.lon = lon
        self.timestamp = timestamp
    }
}

/// What is sent: two decimals, about 1 km.
public struct RoundedPosition: Codable, Equatable, Sendable {
    public let lat: Double
    public let lon: Double
}

public enum PositionPolicy {
    public static func rounded(_ fix: Fix) -> RoundedPosition {
        RoundedPosition(lat: round2(fix.lat), lon: round2(fix.lon))
    }

    /// Send when nothing was ever sent, or when the rounded position changed (the phone moved about a
    /// kilometer). A still phone sends nothing; the server needs no heartbeat (contract, section 3).
    public static func shouldSend(_ position: RoundedPosition, lastSent: RoundedPosition?) -> Bool {
        position != lastSent
    }

    private static func round2(_ value: Double) -> Double { (value * 100).rounded() / 100 }
}
