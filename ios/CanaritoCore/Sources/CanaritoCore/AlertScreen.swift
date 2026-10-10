import Foundation

/// What the alert screen shows, decided here so the view only draws it.
public struct AlertScreen: Equatable, Sendable {
    public enum Kind: Equatable, Sendable { case alert, late, test }

    public enum Elapsed: Equatable, Sendable {
        case seconds(Int), minutes(Int)
    }

    public let kind: Kind
    public let title: String
    public let body: String
    public let magnitudeText: String?
    public let elapsed: Elapsed?
    /// The protective pose and the guide's line: on an on-time alert and on a test, which teaches the pose.
    /// A late alert is already over, so it shows the aftershock line instead.
    public let showsProtectiveLine: Bool
    /// Steps for after the shaking, only after an alert that was on time.
    public let showsAfterSteps: Bool

    public init(_ alert: EarthquakeAlert, now: Date, locale: Locale) {
        kind = alert.isTest ? .test : alert.isLate ? .late : .alert
        title = alert.title
        body = alert.body
        magnitudeText = alert.magnitudeText(locale: locale)
        elapsed = alert.occurredAt.map { Self.elapsed(since: $0, now: now) }
        showsProtectiveLine = kind != .late
        showsAfterSteps = kind == .alert
    }

    public static func elapsed(since occurredAt: Date, now: Date) -> Elapsed {
        let seconds = max(0, Int(now.timeIntervalSince(occurredAt)))
        return seconds < 60 ? .seconds(seconds) : .minutes(seconds / 60)
    }

    public static let afterSteps: [Pictogram] = [.health, .evacuation, .aftershocks]
}
