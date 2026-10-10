#if DEBUG
import Foundation

/// `-fakeGateway YES` on launch: the app's relay and server calls are answered here, in process, so a
/// Simulator run or a UI test needs no server and can never reach a live host. Answers follow
/// docs/app-contract.md.
final class FakeGateway: URLProtocol, @unchecked Sendable {
    static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [FakeGateway.self]
        return URLSession(configuration: configuration)
    }

    static func answer(method: String, path: String) -> (status: Int, body: String) {
        switch (method, path) {
        case ("POST", "/v1/handles"): (200, #"{"handle":"fake-handle"}"#)
        case ("POST", "/v1/pair"): (200, #"{"device_id":"d_fake","device_key":"fake-key","receptor":"casa","language":"es"}"#)
        case ("PUT", "/v1/device"), ("DELETE", "/v1/device"), ("POST", "/v1/position"), ("POST", "/v1/test"): (204, "")
        case ("GET", "/v1/status"): (200, #"{"receptor":"casa","covered":true,"receptor_up":true,"relay_ok":true,"following":true}"#)
        default: (404, #"{"error":"bad_request"}"#)
        }
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func stopLoading() {}

    override func startLoading() {
        guard let url = request.url else { return client?.urlProtocol(self, didFailWithError: URLError(.badURL)) ?? () }
        let (status, body) = Self.answer(method: request.httpMethod ?? "GET", path: url.path)
        let response = HTTPURLResponse(url: url, statusCode: status, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
}
#endif
