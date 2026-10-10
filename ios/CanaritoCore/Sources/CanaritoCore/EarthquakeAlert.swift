import Foundation

/// An alert push (docs/app-contract.md, section 4).
public struct EarthquakeAlert: Equatable, Sendable {
    /// Same for the same alert: the server can send twice after a reconnect.
    public let id: String
    public let title: String
    /// The receptor's own words, in its language. The app shows them as they are.
    public let body: String
    public let magnitude: Double?
    public let occurredAt: Date?
    public let sentAt: Date
    public let isLate: Bool
    public let isTest: Bool

    /// `apns-expiration` is `sent_at + 180`: after that the warning no longer helps anyone take cover.
    public static let lifetime: TimeInterval = 180
    /// Older than this at send time and the quake has already struck for most people.
    public static let lateAfter: TimeInterval = 60

    public init(id: String, title: String, body: String, magnitude: Double? = nil, occurredAt: Date? = nil,
                sentAt: Date, isLate: Bool? = nil, isTest: Bool = false) {
        self.id = id
        self.title = title
        self.body = body
        self.magnitude = magnitude
        self.occurredAt = occurredAt
        self.sentAt = sentAt
        self.isTest = isTest
        self.isLate = isLate ?? occurredAt.map { sentAt.timeIntervalSince($0) > Self.lateAfter } ?? false
    }

    public func isActive(at now: Date) -> Bool { now < sentAt + Self.lifetime }

    /// "M5.4" in English, "M5,4" in Spanish: the phone's decimal separator.
    public func magnitudeText(locale: Locale) -> String? {
        magnitude.map { "M" + $0.formatted(.number.precision(.fractionLength(1)).locale(locale)) }
    }
}

/// Alerts already shown, so a repeat from the server does not ring twice.
public struct SeenAlerts: Sendable {
    static let key = "seen-alert-ids"
    static let limit = 50
    private let store: any KeyValueStore

    public init(store: any KeyValueStore) { self.store = store }

    /// True the first time an id is marked, false every time after.
    public func markSeen(_ id: String) -> Bool {
        var ids = (store.data(forKey: Self.key).flatMap { try? JSONDecoder().decode([String].self, from: $0) }) ?? []
        guard !ids.contains(id) else { return false }
        ids.append(id)
        store.set(data: try? JSONEncoder().encode(ids.suffix(Self.limit)), forKey: Self.key)
        return true
    }
}
