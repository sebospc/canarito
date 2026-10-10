import Foundation

public enum NotificationAccess: Equatable, Sendable {
    case notDetermined, denied, granted
}

public enum LocationAccess: Equatable, Sendable {
    case notDetermined, denied, whileUsing, always
}

/// Did the server accept this phone's push handle yet.
public enum Registration: Equatable, Sendable {
    case pending, registered
}

/// Last answer of `GET /v1/status`. Never persisted: a new launch starts at `.unknown`.
public enum StatusOutcome: Equatable, Sendable {
    case unknown
    case ok(ServerStatus, at: Date)
    case failed
    /// 401: the server removed this phone.
    case notPaired
}

/// What the home screen shows.
public enum HomeState: Equatable, Sendable {
    case notSetUp
    /// Paired, first answer not in yet.
    case checking
    case covered
    case notCovered
    case alert(EarthquakeAlert)
    case error(Problem)

    public enum Problem: Equatable, Sendable {
        case notificationsOff
        /// Alerts arrive, but a Focus may silence them.
        case timeSensitiveOff
        case locationOff
        /// The server has not accepted the push handle: no alert can reach this phone.
        case notRegistered
        case serverUnreachable
        case receptorDown
        case relayDown
        /// The server forgot this phone.
        case removedByServer
    }
}

public struct HomeInputs: Sendable {
    public var pairing: Pairing?
    public var notifications: NotificationAccess
    public var timeSensitiveOn: Bool
    public var location: LocationAccess
    public var registration: Registration
    public var status: StatusOutcome
    public var alert: EarthquakeAlert?
    public var now: Date

    public init(pairing: Pairing?, notifications: NotificationAccess, timeSensitiveOn: Bool = true, location: LocationAccess,
                registration: Registration, status: StatusOutcome, alert: EarthquakeAlert? = nil, now: Date) {
        self.pairing = pairing
        self.notifications = notifications
        self.timeSensitiveOn = timeSensitiveOn
        self.location = location
        self.registration = registration
        self.status = status
        self.alert = alert
        self.now = now
    }
}

extension HomeState {
    /// How old an answer can be before it counts as no answer. The app asks every minute while open.
    public static let statusFreshness: TimeInterval = 10 * 60

    /// The only place that decides the screen. Anything unknown or broken ends in `.error`, never in
    /// a green state: a silent failure is worse than a loud one.
    public static func derive(_ inputs: HomeInputs) -> HomeState {
        if let alert = inputs.alert, alert.isActive(at: inputs.now) { return .alert(alert) }
        guard inputs.pairing != nil, inputs.notifications != .notDetermined, inputs.location != .notDetermined
        else { return .notSetUp }
        if inputs.status == .notPaired { return .error(.removedByServer) }
        if inputs.notifications == .denied { return .error(.notificationsOff) }
        if inputs.location == .denied { return .error(.locationOff) }
        if inputs.registration == .pending { return .error(.notRegistered) }

        switch inputs.status {
        case .unknown: return .checking
        case .failed, .notPaired: return .error(.serverUnreachable)
        case .ok(let status, let at):
            if inputs.now.timeIntervalSince(at) > statusFreshness { return .error(.serverUnreachable) }
            if !status.relayOK { return .error(.relayDown) }
            if !status.receptorUp { return .error(.receptorDown) }
            if !status.covered { return .notCovered }
            if !inputs.timeSensitiveOn { return .error(.timeSensitiveOff) }
            return .covered
        }
    }

    /// With location "While using" only, the phone follows the area of the last app open, not the
    /// person. Shown under any state where a following receptor matters.
    public static func showsTravelWarning(location: LocationAccess, status: StatusOutcome) -> Bool {
        guard location == .whileUsing, case .ok(let status, _) = status else { return false }
        return status.following
    }
}
