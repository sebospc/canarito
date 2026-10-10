import XCTest
@testable import CanaritoCore

final class PairingCodeTests: XCTestCase {
    private let secret = String(repeating: "3f", count: 16)
    private let sid = String(repeating: "a1", count: 16)

    private func link(v: String = "1", server: String = "https%3A%2F%2Fcanarito.example.org", relay: String = "https%3A%2F%2Frelay.example.org",
                      secret: String? = nil, sid: String? = nil) -> String {
        "canarito://pair?v=\(v)&server=\(server)&secret=\(secret ?? self.secret)&relay=\(relay)&sid=\(sid ?? self.sid)"
    }

    func testReadsTheContractExample() throws {
        let invite = try PairingCode.parse(link())
        XCTAssertEqual(invite.server.absoluteString, "https://canarito.example.org")
        XCTAssertEqual(invite.relay.absoluteString, "https://relay.example.org")
        XCTAssertEqual(invite.secret, secret)
        XCTAssertEqual(invite.serverID, sid)
    }

    func testTrailingSlashIsDroppedBecauseCallsAppendV1() throws {
        let invite = try PairingCode.parse(link(server: "https%3A%2F%2Fcanarito.example.org%2F"))
        XCTAssertEqual(invite.server.absoluteString, "https://canarito.example.org")
    }

    func testPastedTextWithSpacesIsAccepted() throws {
        XCTAssertNoThrow(try PairingCode.parse("  " + link() + "\n"))
    }

    func testAnotherVersionSaysUpdateTheApp() {
        XCTAssertThrowsError(try PairingCode.parse(link(v: "2"))) { XCTAssertEqual($0 as? PairingCodeError, .updateTheApp) }
    }

    func testNotACanaritoLink() {
        for text in ["https://example.org", "canarito://other?v=1", "hello", ""] {
            XCTAssertThrowsError(try PairingCode.parse(text), text) { XCTAssertEqual($0 as? PairingCodeError, .notCanarito) }
        }
    }

    func testMalformedParameters() {
        XCTAssertThrowsError(try PairingCode.parse(link(secret: "short"))) { XCTAssertEqual($0 as? PairingCodeError, .malformed) }
        XCTAssertThrowsError(try PairingCode.parse(link(sid: String(repeating: "z", count: 32)))) { XCTAssertEqual($0 as? PairingCodeError, .malformed) }
        XCTAssertThrowsError(try PairingCode.parse("canarito://pair?server=x")) { XCTAssertEqual($0 as? PairingCodeError, .malformed) }
    }

    func testPlainHTTPIsRefusedExceptLocalInDebug() throws {
        let http = link(server: "http%3A%2F%2Fcanarito.example.org")
        XCTAssertThrowsError(try PairingCode.parse(http)) { XCTAssertEqual($0 as? PairingCodeError, .insecure) }
        XCTAssertThrowsError(try PairingCode.parse(http, allowsLocalHTTP: true)) { XCTAssertEqual($0 as? PairingCodeError, .insecure) }
        let local = link(server: "http%3A%2F%2Flocalhost%3A8787", relay: "http%3A%2F%2F127.0.0.1%3A8788")
        XCTAssertThrowsError(try PairingCode.parse(local)) { XCTAssertEqual($0 as? PairingCodeError, .insecure) }
        XCTAssertEqual(try PairingCode.parse(local, allowsLocalHTTP: true).server.absoluteString, "http://localhost:8787")
    }
}
