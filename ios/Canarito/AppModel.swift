import BackgroundTasks
import CanaritoAdapters
import CanaritoCore
import Observation
import OSLog
import SwiftUI
import UserNotifications

/// Why a pairing attempt did not finish, in words the screen can use.
enum PairingProblem: Equatable {
    case notCanarito, updateTheApp, insecure, malformed
    /// The pairing secret was wrong, used or expired.
    case badSecret
    /// Neither the relay nor the server answered.
    case unreachable
    /// The phone has no APNs token, so no alert could ever reach it.
    case noPushToken
    /// iOS refused the APNs registration; the text is the system's error, shown so a tester can report it.
    case pushRegistrationFailed(String)
    case other(String)
}

enum TestAlertStatus: Equatable {
    case idle, sending, sent, tooSoon, failed
}

/// The composition root and the one place that holds app state. The rules live in CanaritoCore.
@MainActor @Observable
final class AppModel {
    static let refreshTaskIdentifier = "app.canarito.refresh"

    private enum Key {
        static let pairing = "pairing", deviceKey = "device-key", registeredToken = "registered-token"
        static let lastPosition = "last-sent-position", introDone = "intro-done", notifiedProblem = "notified-problem"
    }

    private let service: any CanaritoService
    private let store: any KeyValueStore
    private let secrets: any SecretStore
    private let seenAlerts: SeenAlerts
    private let location = LocationService()
    private let log = Logger(subsystem: Bundle.main.bundleIdentifier ?? "Canarito", category: "app")

    private(set) var pairing: Pairing?
    private(set) var notifications: NotificationAccess = .notDetermined
    private(set) var timeSensitiveOn = true
    private(set) var locationAccess: LocationAccess = .notDetermined
    private(set) var apnsToken: String?
    private(set) var apnsFailed = false
    private(set) var apnsError: String?
    private(set) var status: StatusOutcome = .unknown
    private(set) var alert: EarthquakeAlert?
    private(set) var alertCameFromTap = false
    private(set) var now = Date()
    /// Stored, not read from the store on the fly, so the screen changes the moment the intro ends.
    private(set) var hasSeenIntro = false
    private(set) var testAlertStatus: TestAlertStatus = .idle
    /// A canarito://pair link that arrived by URL: the person confirms before the secret is spent.
    var pendingInvite: PairingInvite?

    private var registeredToken: String?
    private var lastSentPosition: RoundedPosition?
    private var pendingPosition: RoundedPosition?
    private var pollTask: Task<Void, Never>?
    private var isSyncingToken = false

    init(service: any CanaritoService, store: any KeyValueStore, secrets: any SecretStore) {
        self.service = service
        self.store = store
        self.secrets = secrets
        seenAlerts = SeenAlerts(store: store)
        pairing = store.data(forKey: Key.pairing).flatMap { try? JSONDecoder().decode(Pairing.self, from: $0) }
        registeredToken = store.string(forKey: Key.registeredToken)
        hasSeenIntro = store.string(forKey: Key.introDone) != nil
        lastSentPosition = store.data(forKey: Key.lastPosition).flatMap { try? JSONDecoder().decode(RoundedPosition.self, from: $0) }
        location.onFix = { [unowned self] fix in gotFix(fix) }
        location.onAccess = { [unowned self] access in locationAccess = access }
    }

    // MARK: what the screen shows

    var state: HomeState {
        HomeState.derive(HomeInputs(pairing: pairing, notifications: notifications, timeSensitiveOn: timeSensitiveOn, location: locationAccess,
                                    registration: registration, status: status, alert: alert, now: now))
    }

    /// A token that has not arrived yet is not a mismatch; one that failed to arrive is.
    private var registration: Registration {
        guard let registeredToken, !apnsFailed, apnsToken == nil || apnsToken == registeredToken else { return .pending }
        return .registered
    }

    var locationNotice: LocationNotice? { HomeState.locationNotice(location: locationAccess, status: status) }
    var deviceKey: String? { secrets.secret(forKey: Key.deviceKey) }

    // MARK: lifecycle

    func launched() {
        location.start()
        refreshPermissions()
        if notifications == .granted { UIApplication.shared.registerForRemoteNotifications() }
    }

    func becameActive() {
        pollTask?.cancel()
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: .seconds(60))
            }
        }
    }

    func resignedActive() { pollTask?.cancel() }

    func refresh() async {
        now = Date()
        refreshPermissions()
        location.requestFreshFix()
        await syncToken()
        await sendPendingPosition()
        await refreshStatus()
    }

    // MARK: permissions

    func refreshPermissions() {
        Task {
            let settings = await UNUserNotificationCenter.current().notificationSettings()
            notifications = switch settings.authorizationStatus {
            case .notDetermined: .notDetermined
            case .authorized, .ephemeral: .granted
            // Provisional is quiet delivery: for an earthquake alert that is as bad as off.
            case .denied, .provisional: .denied
            @unknown default: .denied
            }
            timeSensitiveOn = settings.timeSensitiveSetting != .disabled
            locationAccess = location.access
        }
    }

    /// First run: notifications, then location. A refusal never blocks the next step; the home screen
    /// says what is off.
    func askPermissions() async {
        _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: Self.notificationOptions)
        refreshPermissions()
        UIApplication.shared.registerForRemoteNotifications()
        location.requestWhenInUse()
        // iOS shows the "Always" offer by itself once "While using" is granted.
        for _ in 0..<120 where location.access == .notDetermined { try? await Task.sleep(for: .milliseconds(500)) }
        location.requestAlwaysOnce()
        store.set(string: "1", forKey: Key.introDone)
        hasSeenIntro = true
        refreshPermissions()
    }

    /// `.criticalAlert` only once Apple grants the entitlement (build flag CRITICAL_ALERTS). Never
    /// `.provisional`: provisional notifications arrive quietly, the opposite of an alert.
    static var notificationOptions: UNAuthorizationOptions {
        #if CRITICAL_ALERTS
        [.alert, .sound, .badge, .criticalAlert]
        #else
        [.alert, .sound, .badge]
        #endif
    }

    // MARK: push token

    func tokenArrived(_ data: Data) {
        apnsToken = data.map { String(format: "%02x", $0) }.joined()
        apnsFailed = false
        apnsError = nil
        Task { await syncToken() }
    }

    func tokenFailed(_ error: any Error) {
        // The Simulator has no APNs: a UI test with a fake token must not be overruled by that failure.
        guard !Samples.fakeToken else { return }
        apnsFailed = true
        apnsError = error.localizedDescription
        log.error("APNs registration failed: \(error.localizedDescription, privacy: .public)")
    }

    private var pushEnvironment: PushEnvironment {
        #if DEBUG
        .sandbox
        #else
        .production
        #endif
    }

    /// A new APNs token gives a new handle (contract 2c). One attempt per call; the one-minute loop is the retry.
    private func syncToken() async {
        guard let pairing, let key = deviceKey, let token = apnsToken, token != registeredToken, !isSyncingToken else { return }
        isSyncingToken = true
        defer { isSyncingToken = false }
        do throws(ServerFailure) {
            let handle = try await service.handle(relay: pairing.relay, serverID: pairing.serverID, apnsToken: token, environment: pushEnvironment)
            try await service.updateHandle(handle, pairing: pairing, deviceKey: key)
            registeredToken = token
            store.set(string: token, forKey: Key.registeredToken)
        } catch {
            noteFailure(error)
        }
    }

    // MARK: pairing

    func pair(_ invite: PairingInvite) async -> PairingProblem? {
        guard let token = await waitForToken() else {
            return apnsFailed ? .pushRegistrationFailed(apnsError ?? "") : .noPushToken
        }
        do throws(ServerFailure) {
            let handle = try await service.handle(relay: invite.relay, serverID: invite.serverID, apnsToken: token, environment: pushEnvironment)
            let result = try await service.pair(invite: invite, handle: handle, deviceName: UIDevice.current.name)
            let paired = Pairing(server: invite.server, relay: invite.relay, serverID: invite.serverID, deviceID: result.deviceID,
                                 receptor: result.receptor, language: result.language)
            secrets.set(secret: result.deviceKey, forKey: Key.deviceKey)
            store.set(data: try? JSONEncoder().encode(paired), forKey: Key.pairing)
            store.set(string: token, forKey: Key.registeredToken)
            store.set(data: nil, forKey: Key.lastPosition)
            pairing = paired
            registeredToken = token
            lastSentPosition = nil
            status = .unknown
            pendingInvite = nil
        } catch .rejected(let code) {
            return code == "bad_secret" ? .badSecret : .other(code)
        } catch {
            return .unreachable
        }
        // Contract section 3: one position right after pairing.
        location.start()
        location.requestFreshFix()
        await refreshStatus()
        return nil
    }

    func receive(link text: String) -> PairingProblem? {
        do throws(PairingCodeError) {
            pendingInvite = try PairingCode.parse(text, allowsLocalHTTP: Self.allowsLocalHTTP)
            return nil
        } catch {
            return switch error {
            case .notCanarito: .notCanarito
            case .updateTheApp: .updateTheApp
            case .insecure: .insecure
            case .malformed: .malformed
            }
        }
    }

    private static var allowsLocalHTTP: Bool {
        #if DEBUG
        true
        #else
        false
        #endif
    }

    /// Pairing can start before the first-run permissions did (or on a slow network), so it asks for the
    /// token itself instead of waiting for a registration nobody started.
    private func waitForToken() async -> String? {
        if apnsToken == nil {
            apnsFailed = false
            UIApplication.shared.registerForRemoteNotifications()
        }
        return await Polling.wait(attempts: 120, interval: .milliseconds(250), giveUp: { apnsFailed }) { apnsToken }
    }

    /// Returns false when the server could not be told; the caller may then forget the pairing anyway.
    func unpair(force: Bool) async -> Bool {
        if let pairing, let key = deviceKey, !force {
            do throws(ServerFailure) {
                try await service.removeDevice(pairing: pairing, deviceKey: key)
            } catch .unauthorized {
                // Already forgotten by the server.
            } catch {
                return false
            }
        }
        forgetPairing()
        return true
    }

    private func forgetPairing() {
        location.stop()
        secrets.set(secret: nil, forKey: Key.deviceKey)
        [Key.pairing, Key.registeredToken, Key.lastPosition].forEach { store.set(data: nil, forKey: $0) }
        pairing = nil
        registeredToken = nil
        lastSentPosition = nil
        pendingPosition = nil
        status = .unknown
        testAlertStatus = .idle
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [Self.deadManIdentifier])
    }

    // MARK: position

    private func gotFix(_ fix: Fix) {
        guard pairing != nil else { return }
        pendingPosition = PositionPolicy.rounded(fix)
        Task { await sendPendingPosition() }
    }

    private func sendPendingPosition() async {
        guard let pairing, let key = deviceKey, let position = pendingPosition else { return }
        guard PositionPolicy.shouldSend(position, lastSent: lastSentPosition) else { pendingPosition = nil; return }
        // A location wake-up has seconds: ask iOS to keep the process until the request ends.
        let background = UIApplication.shared.beginBackgroundTask(withName: "send-position")
        defer { UIApplication.shared.endBackgroundTask(background) }
        do throws(ServerFailure) {
            try await service.sendPosition(position, pairing: pairing, deviceKey: key)
            lastSentPosition = position
            store.set(data: try? JSONEncoder().encode(position), forKey: Key.lastPosition)
            pendingPosition = nil
        } catch {
            // Kept as pending: a retryable failure goes out on the next loop, a rejected one is dropped.
            if case .rejected = error { pendingPosition = nil }
            noteFailure(error)
        }
    }

    // MARK: status

    func refreshStatus() async {
        guard let pairing, let key = deviceKey else { status = .unknown; return }
        do throws(ServerFailure) {
            let answer = try await service.status(pairing: pairing, deviceKey: key)
            now = Date()
            status = .ok(answer, at: now)
            scheduleDeadManReminder()
        } catch .unauthorized {
            status = .notPaired
        } catch {
            status = .failed
        }
    }

    private func noteFailure(_ failure: ServerFailure) {
        if failure == .unauthorized { status = .notPaired }
    }

    // MARK: alerts

    /// True the first time this alert is seen: the caller shows the banner and the sound for it only then.
    func received(_ incoming: EarthquakeAlert, fromTap: Bool = false) -> Bool {
        let isNew = seenAlerts.markSeen(incoming.id)
        now = Date()
        guard incoming.isActive(at: now) else { return isNew }
        if isNew || fromTap {
            alert = incoming
            alertCameFromTap = fromTap
        }
        let remaining = incoming.sentAt.addingTimeInterval(EarthquakeAlert.lifetime).timeIntervalSinceNow
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(max(remaining, 0) + 0.5))
            self?.now = Date()
            if self?.alert == incoming { self?.alert = nil }
        }
        return isNew
    }

    func dismissAlert() { alert = nil }

    func sendTestAlert() async {
        guard let pairing, let key = deviceKey, testAlertStatus != .sending else { return }
        testAlertStatus = .sending
        do throws(TestAlertFailure) {
            try await service.requestTestAlert(pairing: pairing, deviceKey: key)
            testAlertStatus = .sent
        } catch {
            testAlertStatus = error == .tooSoon ? .tooSoon : .failed
            if case .failed(.unauthorized) = error { status = .notPaired }
        }
    }

    // MARK: safety nets

    private static let deadManIdentifier = "dead-man"

    /// If the app has not heard from the server for 8 days (it was never opened, or iOS stopped waking it),
    /// say so. Rescheduled after every answer, so it only fires when the answers stopped.
    private func scheduleDeadManReminder() {
        let content = UNMutableNotificationContent()
        content.title = String(localized: "Comprueba tus avisos de sismo")
        content.body = String(localized: "Hace 8 días que Canarito no habla con tu servidor. Abre la app para comprobar que sigues cubierto.")
        content.interruptionLevel = .timeSensitive
        content.sound = .default
        let request = UNNotificationRequest(identifier: Self.deadManIdentifier, content: content,
                                            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 8 * 24 * 3600, repeats: false))
        UNUserNotificationCenter.current().add(request)
    }

    static func scheduleBackgroundRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: refreshTaskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 2 * 3600)
        try? BGTaskScheduler.shared.submit(request)
    }

    /// iOS wakes the app now and then. When the server or the push path is broken, say it once with a
    /// local notification: silence must not look like safety.
    func backgroundRefresh() async {
        await refresh()
        let problem: HomeState.Problem? = if case .error(let problem) = state { problem } else { nil }
        let serverProblems: [HomeState.Problem] = [.serverUnreachable, .receptorDown, .relayDown, .removedByServer, .notRegistered]
        guard let problem, serverProblems.contains(problem) else { store.set(string: nil, forKey: Key.notifiedProblem); return }
        let marker = String(describing: problem)
        guard store.string(forKey: Key.notifiedProblem) != marker else { return }
        store.set(string: marker, forKey: Key.notifiedProblem)
        let content = UNMutableNotificationContent()
        content.title = String(localized: "Tus avisos de sismo pueden no llegar")
        content.body = String(localized: "Abre Canarito para ver qué pasa con tu servidor.")
        content.interruptionLevel = .timeSensitive
        content.sound = .default
        try? await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "server-problem", content: content, trigger: nil))
    }
}
