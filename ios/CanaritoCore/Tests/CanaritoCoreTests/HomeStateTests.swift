import XCTest
@testable import CanaritoCore

final class HomeStateTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_791_650_000)
    private let pairing = Pairing(server: URL(string: "https://canarito.example.org")!, relay: URL(string: "https://relay.example.org")!,
                                  serverID: "s", deviceID: "d", receptor: "casa", language: "es")

    private func status(covered: Bool = true, receptorUp: Bool = true, relayOK: Bool = true, following: Bool = true) -> ServerStatus {
        ServerStatus(receptor: "casa", covered: covered, receptorUp: receptorUp, relayOK: relayOK, following: following)
    }

    private func inputs(pairing: Pairing?? = nil, notifications: NotificationAccess = .granted, timeSensitiveOn: Bool = true,
                        location: LocationAccess = .always, registration: Registration = .registered,
                        status: StatusOutcome? = nil, alert: EarthquakeAlert? = nil) -> HomeInputs {
        HomeInputs(pairing: pairing ?? self.pairing, notifications: notifications, timeSensitiveOn: timeSensitiveOn, location: location,
                   registration: registration, status: status ?? .ok(self.status(), at: now), alert: alert, now: now)
    }

    private func alert(sentAgo: TimeInterval) -> EarthquakeAlert {
        EarthquakeAlert(id: "e1", title: "Alerta de sismo", body: "Sismo M5.4", sentAt: now - sentAgo)
    }

    func testAllGoodIsCovered() {
        XCTAssertEqual(HomeState.derive(inputs()), .covered)
    }

    func testNotPairedOrNeverAskedIsNotSetUp() {
        XCTAssertEqual(HomeState.derive(inputs(pairing: .some(nil))), .notSetUp)
        XCTAssertEqual(HomeState.derive(inputs(notifications: .notDetermined)), .notSetUp)
        XCTAssertEqual(HomeState.derive(inputs(location: .notDetermined)), .notSetUp)
    }

    func testAnActiveAlertWinsOverEverything() {
        let live = alert(sentAgo: 5)
        XCTAssertEqual(HomeState.derive(inputs(pairing: .some(nil), status: .failed, alert: live)), .alert(live))
    }

    func testAnExpiredAlertNoLongerCoversTheScreen() {
        XCTAssertEqual(HomeState.derive(inputs(alert: alert(sentAgo: 181))), .covered)
    }

    func testEachProblemIsLoudNeverGreen() {
        XCTAssertEqual(HomeState.derive(inputs(notifications: .denied)), .error(.notificationsOff))
        XCTAssertEqual(HomeState.derive(inputs(location: .denied)), .error(.locationOff))
        XCTAssertEqual(HomeState.derive(inputs(registration: .pending)), .error(.notRegistered))
        XCTAssertEqual(HomeState.derive(inputs(status: .failed)), .error(.serverUnreachable))
        XCTAssertEqual(HomeState.derive(inputs(status: .notPaired)), .error(.removedByServer))
        XCTAssertEqual(HomeState.derive(inputs(status: .ok(status(relayOK: false), at: now))), .error(.relayDown))
        XCTAssertEqual(HomeState.derive(inputs(status: .ok(status(receptorUp: false), at: now))), .error(.receptorDown))
        XCTAssertEqual(HomeState.derive(inputs(timeSensitiveOn: false)), .error(.timeSensitiveOff))
    }

    func testAnOldAnswerCountsAsNoAnswer() {
        let old = StatusOutcome.ok(status(), at: now - HomeState.statusFreshness - 1)
        XCTAssertEqual(HomeState.derive(inputs(status: old)), .error(.serverUnreachable))
    }

    func testNoAnswerYetIsChecking() {
        XCTAssertEqual(HomeState.derive(inputs(status: .unknown)), .checking)
    }

    func testNotCoveredIsItsOwnStateAndBrokenWinsOverIt() {
        XCTAssertEqual(HomeState.derive(inputs(status: .ok(status(covered: false), at: now))), .notCovered)
        XCTAssertEqual(HomeState.derive(inputs(status: .ok(status(covered: false, relayOK: false), at: now))), .error(.relayDown))
    }

    func testTravelWarningOnlyWithWhileUsingAndAFollowingReceptor() {
        let following = StatusOutcome.ok(status(), at: now)
        XCTAssertTrue(HomeState.showsTravelWarning(location: .whileUsing, status: following))
        XCTAssertFalse(HomeState.showsTravelWarning(location: .always, status: following))
        XCTAssertFalse(HomeState.showsTravelWarning(location: .whileUsing, status: .ok(status(following: false), at: now)))
        XCTAssertFalse(HomeState.showsTravelWarning(location: .whileUsing, status: .failed))
    }
}
