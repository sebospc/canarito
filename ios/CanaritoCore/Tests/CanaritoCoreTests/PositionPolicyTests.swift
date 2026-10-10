import XCTest
@testable import CanaritoCore

final class PositionPolicyTests: XCTestCase {
    private func fix(_ lat: Double, _ lon: Double) -> Fix { Fix(lat: lat, lon: lon, timestamp: Date(timeIntervalSince1970: 0)) }

    func testRoundsToTwoDecimalsBeforeAnythingIsSent() {
        XCTAssertEqual(PositionPolicy.rounded(fix(4.71234, -74.07456)), RoundedPosition(lat: 4.71, lon: -74.07))
        XCTAssertEqual(PositionPolicy.rounded(fix(4.715, -74.075)).lat, 4.72)
        XCTAssertEqual(PositionPolicy.rounded(fix(-33.4489, 151.2093)), RoundedPosition(lat: -33.45, lon: 151.21))
    }

    func testTheRoundedValueNeverCarriesTheExactOne() throws {
        let sent = PositionPolicy.rounded(fix(4.712345678, -74.074567891))
        let json = String(decoding: try JSONEncoder().encode(sent), as: UTF8.self)
        XCTAssertFalse(json.contains("4.7123"))
        XCTAssertFalse(json.contains("74.0745"))
    }

    func testSendsFirstThenOnlyWhenTheRoundedPositionChanges() {
        let home = PositionPolicy.rounded(fix(4.711, -74.072))
        XCTAssertTrue(PositionPolicy.shouldSend(home, lastSent: nil))
        XCTAssertFalse(PositionPolicy.shouldSend(PositionPolicy.rounded(fix(4.7134, -74.0721)), lastSent: home), "same 1 km cell")
        XCTAssertTrue(PositionPolicy.shouldSend(PositionPolicy.rounded(fix(4.73, -74.072)), lastSent: home))
    }
}
