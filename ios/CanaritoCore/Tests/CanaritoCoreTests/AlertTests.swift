import XCTest
@testable import CanaritoAdapters
@testable import CanaritoCore

final class AlertTests: XCTestCase {
    private let sentAt = Date(timeIntervalSince1970: 1_791_650_000)

    private func payload(canarito: [String: Any]? = nil, body: String? = "Sismo M5.4 cerca de tu zona. Protégete ahora.") -> [AnyHashable: Any] {
        var alert: [String: Any] = ["title": "Alerta de sismo"]
        if let body { alert["body"] = body }
        return ["aps": ["alert": alert],
                "canarito": canarito ?? ["v": 1, "id": "ntfy-1", "receptor": "casa", "lang": "es", "sent_at": 1_791_650_000]]
    }

    func testReadsTheContractPayload() throws {
        let alert = try XCTUnwrap(EarthquakeAlert(userInfo: payload()))
        XCTAssertEqual(alert.id, "ntfy-1")
        XCTAssertEqual(alert.title, "Alerta de sismo")
        XCTAssertEqual(alert.body, "Sismo M5.4 cerca de tu zona. Protégete ahora.")
        XCTAssertEqual(alert.sentAt, sentAt)
        XCTAssertNil(alert.magnitude)
        XCTAssertFalse(alert.isLate)
        XCTAssertFalse(alert.isTest)
    }

    func testReadsMagnitudeOriginTimeLateAndTest() throws {
        let alert = try XCTUnwrap(EarthquakeAlert(userInfo: payload(canarito: [
            "id": "x", "sent_at": 1_791_650_000, "magnitude": 5.4, "occurred_at": 1_791_649_900, "late": true, "test": true])))
        XCTAssertEqual(alert.magnitude, 5.4)
        XCTAssertEqual(alert.occurredAt, sentAt - 100)
        XCTAssertTrue(alert.isLate)
        XCTAssertTrue(alert.isTest)
    }

    func testADrillIsMarkedAndKeepsTheFullAlertScreen() throws {
        let drill = try XCTUnwrap(EarthquakeAlert(userInfo: payload(canarito: ["id": "drill-1", "sent_at": 1_791_650_000, "drill": true])))
        XCTAssertTrue(drill.isDrill)
        let screen = AlertScreen(drill, now: sentAt, locale: Locale(identifier: "es"))
        XCTAssertEqual(screen.kind, .drill)
        XCTAssertTrue(screen.showsProtectiveLine)
        XCTAssertTrue(screen.showsAfterSteps)
        XCTAssertFalse(try XCTUnwrap(EarthquakeAlert(userInfo: payload())).isDrill)
    }

    func testLateIsInferredFromTheOriginTimeWhenTheFlagIsMissing() throws {
        let late = try XCTUnwrap(EarthquakeAlert(userInfo: payload(canarito: ["id": "x", "sent_at": 1_791_650_000, "occurred_at": 1_791_649_900])))
        let onTime = try XCTUnwrap(EarthquakeAlert(userInfo: payload(canarito: ["id": "y", "sent_at": 1_791_650_000, "occurred_at": 1_791_649_990])))
        XCTAssertTrue(late.isLate)
        XCTAssertFalse(onTime.isLate)
    }

    func testNotAnAlertIsNil() {
        XCTAssertNil(EarthquakeAlert(userInfo: ["aps": ["alert": ["body": "hola"]]]), "no canarito.id")
        XCTAssertNil(EarthquakeAlert(userInfo: payload(body: nil)), "no text to show")
        XCTAssertNil(EarthquakeAlert(userInfo: payload(body: "")))
    }

    func testTheSameAlertRingsOnce() {
        let seen = SeenAlerts(store: InMemoryStore())
        XCTAssertTrue(seen.markSeen("a"))
        XCTAssertFalse(seen.markSeen("a"))
        XCTAssertTrue(seen.markSeen("b"))
    }

    func testSeenAlertsKeepOnlyTheLatestFifty() {
        let seen = SeenAlerts(store: InMemoryStore())
        for index in 0..<60 { _ = seen.markSeen("id-\(index)") }
        XCTAssertTrue(seen.markSeen("id-0"), "forgotten")
        XCTAssertFalse(seen.markSeen("id-59"))
    }

    func testMagnitudeUsesThePhonesDecimalSeparator() {
        let alert = EarthquakeAlert(id: "m", title: "", body: "b", magnitude: 5.4, sentAt: sentAt)
        XCTAssertEqual(alert.magnitudeText(locale: Locale(identifier: "es_CO")), "M5,4")
        XCTAssertEqual(alert.magnitudeText(locale: Locale(identifier: "en_US")), "M5.4")
    }

    func testScreenKindsAndWhatEachShows() {
        let now = sentAt + 12
        let onTime = AlertScreen(EarthquakeAlert(id: "1", title: "t", body: "b", magnitude: 5.4, occurredAt: sentAt - 2, sentAt: sentAt),
                                 now: now, locale: Locale(identifier: "en_US"))
        XCTAssertEqual(onTime.kind, .alert)
        XCTAssertTrue(onTime.showsProtectiveLine)
        XCTAssertTrue(onTime.showsAfterSteps)
        XCTAssertEqual(onTime.elapsed, .seconds(14))

        let late = AlertScreen(EarthquakeAlert(id: "2", title: "t", body: "b", sentAt: sentAt, isLate: true), now: now, locale: .current)
        XCTAssertEqual(late.kind, .late)
        XCTAssertFalse(late.showsProtectiveLine)
        XCTAssertFalse(late.showsAfterSteps)

        let test = AlertScreen(EarthquakeAlert(id: "3", title: "t", body: "b", sentAt: sentAt, isTest: true), now: now, locale: .current)
        XCTAssertEqual(test.kind, .test)
        XCTAssertTrue(test.showsProtectiveLine)
        XCTAssertFalse(test.showsAfterSteps)
    }

    func testElapsedSwitchesToMinutes() {
        XCTAssertEqual(AlertScreen.elapsed(since: sentAt, now: sentAt + 59), .seconds(59))
        XCTAssertEqual(AlertScreen.elapsed(since: sentAt, now: sentAt + 125), .minutes(2))
        XCTAssertEqual(AlertScreen.elapsed(since: sentAt, now: sentAt - 5), .seconds(0), "a fast phone clock never shows a negative")
    }
}
