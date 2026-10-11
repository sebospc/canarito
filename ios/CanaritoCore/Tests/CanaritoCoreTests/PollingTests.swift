import XCTest
@testable import CanaritoCore

@MainActor
final class PollingTests: XCTestCase {
    func testReturnsTheValueThatArrivesLate() async {
        var calls = 0
        let found = await Polling.wait(attempts: 10, interval: .milliseconds(1)) { () -> String? in
            calls += 1
            return calls == 4 ? "token" : nil
        }
        XCTAssertEqual(found, "token")
        XCTAssertEqual(calls, 4)
    }

    func testGivesUpAfterTheLastAttempt() async {
        var calls = 0
        let found = await Polling.wait(attempts: 3, interval: .milliseconds(1)) { () -> String? in calls += 1; return nil }
        XCTAssertNil(found)
        XCTAssertEqual(calls, 3)
    }

    func testStopsEarlyWhenToldTheWaitIsPointless() async {
        var calls = 0
        let found = await Polling.wait(attempts: 100, interval: .milliseconds(1), giveUp: { true }) { () -> String? in calls += 1; return nil }
        XCTAssertNil(found)
        XCTAssertEqual(calls, 1)
    }
}
