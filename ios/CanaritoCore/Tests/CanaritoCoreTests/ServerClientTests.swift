import XCTest
@testable import CanaritoAdapters
@testable import CanaritoCore

private final class StubProtocol: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var handler: (@Sendable (URLRequest) -> (Int, String))?
    nonisolated(unsafe) static var seen: [URLRequest] = []
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func stopLoading() {}
    override func startLoading() {
        var request = self.request
        if request.httpBody == nil, let stream = request.httpBodyStream {
            stream.open()
            var data = Data(); var buffer = [UInt8](repeating: 0, count: 1024)
            while stream.hasBytesAvailable { let n = stream.read(&buffer, maxLength: 1024); if n <= 0 { break }; data.append(buffer, count: n) }
            request.httpBody = data
        }
        Self.seen.append(request)
        let (status, body) = Self.handler?(request) ?? (500, "")
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
}

final class ServerClientTests: XCTestCase {
    private let pairing = Pairing(server: URL(string: "https://canarito.example.org")!, relay: URL(string: "https://relay.example.org")!,
                                  serverID: "s", deviceID: "d", receptor: "casa", language: "es")

    private func client(_ handler: @escaping @Sendable (URLRequest) -> (Int, String)) -> ServerClient {
        StubProtocol.handler = handler
        StubProtocol.seen = []
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubProtocol.self]
        return ServerClient(session: URLSession(configuration: configuration))
    }

    func testPairingFollowsTheContractOrder() async throws {
        let client = client { request in
            switch request.url!.path {
            case "/v1/handles": (200, #"{"handle":"H1"}"#)
            case "/v1/pair": (200, #"{"device_id":"d_1","device_key":"KEY","receptor":"casa","language":"en"}"#)
            default: (404, "")
            }
        }
        let invite = try PairingCode.parse("canarito://pair?v=1&server=https%3A%2F%2Fcanarito.example.org&secret=\(String(repeating: "3f", count: 16))&relay=https%3A%2F%2Frelay.example.org&sid=\(String(repeating: "a1", count: 16))")
        let handle = try await client.handle(relay: invite.relay, serverID: invite.serverID, apnsToken: "abcd", environment: .sandbox)
        let result = try await client.pair(invite: invite, handle: handle, deviceName: "iPhone")
        XCTAssertEqual(result, PairResult(deviceID: "d_1", deviceKey: "KEY", receptor: "casa", language: "en"))

        let handlesBody = try JSONSerialization.jsonObject(with: XCTUnwrap(StubProtocol.seen[0].httpBody)) as? [String: String]
        XCTAssertEqual(handlesBody, ["server_id": invite.serverID, "apns_token": "abcd", "environment": "sandbox"])
        XCTAssertEqual(StubProtocol.seen[0].url?.host, "relay.example.org")
        XCTAssertNil(StubProtocol.seen[0].value(forHTTPHeaderField: "Authorization"))
        let pairBody = try JSONSerialization.jsonObject(with: XCTUnwrap(StubProtocol.seen[1].httpBody)) as? [String: String]
        XCTAssertEqual(pairBody?["secret"], invite.secret)
        XCTAssertEqual(pairBody?["handle"], "H1")
    }

    func testPositionIsSentRoundedWithTheBearerKey() async throws {
        let client = client { _ in (204, "") }
        try await client.sendPosition(PositionPolicy.rounded(Fix(lat: 4.71234, lon: -74.07456, timestamp: .now)), pairing: pairing, deviceKey: "KEY")
        let request = StubProtocol.seen[0]
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/v1/position")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer KEY")
        let body = try JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as? [String: Double]
        XCTAssertEqual(body, ["lat": 4.71, "lon": -74.07])
    }

    func testErrorsMapToFailures() async {
        let cases: [(Int, String, ServerFailure)] = [
            (403, #"{"error":"bad_secret"}"#, .rejected(code: "bad_secret")),
            (401, #"{"error":"bad_key"}"#, .unauthorized),
            (429, #"{"error":"slow_down"}"#, .tooMany),
            (503, "", .retryLater),
            (400, "not json", .rejected(code: "http_400")),
        ]
        for (status, body, expected) in cases {
            let client = client { _ in (status, body) }
            do {
                try await client.sendPosition(RoundedPosition(lat: 1, lon: 1), pairing: pairing, deviceKey: "K")
                XCTFail("expected \(expected)")
            } catch {
                XCTAssertEqual(error, expected, "\(status)")
            }
        }
    }

    func testStatusIsRead() async throws {
        let client = client { _ in (200, #"{"receptor":"casa","covered":true,"receptor_up":true,"relay_ok":false,"following":false}"#) }
        let status = try await client.status(pairing: pairing, deviceKey: "K")
        XCTAssertEqual(status, ServerStatus(receptor: "casa", covered: true, receptorUp: true, relayOK: false, following: false))
    }

    func testAnUnreadableStatusIsRejectedNotTrusted() async {
        let client = client { _ in (200, "{}") }
        do { _ = try await client.status(pairing: pairing, deviceKey: "K"); XCTFail("expected failure") } catch {
            XCTAssertEqual(error, .rejected(code: "unreadable_answer"))
        }
    }

    func testTestAlertTooSoon() async {
        let client = client { _ in (429, #"{"error":"slow_down"}"#) }
        do { try await client.requestTestAlert(pairing: pairing, deviceKey: "K"); XCTFail("expected failure") } catch {
            XCTAssertEqual(error, .tooSoon)
        }
    }

    func testNoNetworkIsRetryLater() async {
        let client = client { _ in (0, "") }
        StubProtocol.handler = nil
        let failing = ServerClient(session: URLSession(configuration: { let c = URLSessionConfiguration.ephemeral; c.protocolClasses = []; return c }()))
        _ = client
        do {
            try await failing.sendPosition(RoundedPosition(lat: 1, lon: 1), pairing: Pairing(server: URL(string: "https://nonexistent.invalid")!,
                relay: pairing.relay, serverID: "s", deviceID: "d", receptor: "r", language: "es"), deviceKey: "K")
            XCTFail("expected failure")
        } catch {
            XCTAssertEqual(error, .retryLater)
        }
    }
}
