import CanaritoCore
import Foundation

/// The HTTP adapter for `CanaritoService` (docs/app-contract.md). JSON shapes are private to this file.
public struct ServerClient: CanaritoService {
    private let session: URLSession

    public init(session: URLSession = ServerClient.makeSession()) { self.session = session }

    public static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        // A wake-up from a location change has seconds, not minutes.
        configuration.timeoutIntervalForRequest = 15
        configuration.waitsForConnectivity = false
        return URLSession(configuration: configuration)
    }

    public func handle(relay: URL, serverID: String, apnsToken: String, environment: PushEnvironment) async throws(ServerFailure) -> String {
        struct Body: Encodable { let server_id: String, apns_token: String, environment: String }
        struct Answer: Decodable { let handle: String }
        let body = Body(server_id: serverID, apns_token: apnsToken, environment: environment.rawValue)
        let answer: Answer = try await send(.post, relay, "/v1/handles", body: body)
        return answer.handle
    }

    public func pair(invite: PairingInvite, handle: String, deviceName: String) async throws(ServerFailure) -> PairResult {
        struct Body: Encodable { let secret: String, handle: String, name: String }
        struct Answer: Decodable { let device_id: String, device_key: String, receptor: String, language: String }
        let body = Body(secret: invite.secret, handle: handle, name: String(deviceName.prefix(60)))
        let answer: Answer = try await send(.post, invite.server, "/v1/pair", body: body)
        return PairResult(deviceID: answer.device_id, deviceKey: answer.device_key, receptor: answer.receptor, language: answer.language)
    }

    public func updateHandle(_ handle: String, pairing: Pairing, deviceKey: String) async throws(ServerFailure) {
        struct Body: Encodable { let handle: String }
        try await sendWithoutAnswer(.put, pairing.server, "/v1/device", body: Body(handle: handle), key: deviceKey)
    }

    public func removeDevice(pairing: Pairing, deviceKey: String) async throws(ServerFailure) {
        try await sendWithoutAnswer(.delete, pairing.server, "/v1/device", body: Optional<RoundedPosition>.none, key: deviceKey)
    }

    public func sendPosition(_ position: RoundedPosition, pairing: Pairing, deviceKey: String) async throws(ServerFailure) {
        try await sendWithoutAnswer(.post, pairing.server, "/v1/position", body: position, key: deviceKey)
    }

    public func status(pairing: Pairing, deviceKey: String) async throws(ServerFailure) -> ServerStatus {
        struct Answer: Decodable { let receptor: String, covered: Bool, receptor_up: Bool, relay_ok: Bool, following: Bool }
        let answer: Answer = try await send(.get, pairing.server, "/v1/status", body: Optional<RoundedPosition>.none, key: deviceKey)
        return ServerStatus(receptor: answer.receptor, covered: answer.covered, receptorUp: answer.receptor_up,
                            relayOK: answer.relay_ok, following: answer.following)
    }

    public func requestTestAlert(pairing: Pairing, deviceKey: String) async throws(TestAlertFailure) {
        do {
            try await sendWithoutAnswer(.post, pairing.server, "/v1/test", body: Optional<RoundedPosition>.none, key: deviceKey)
        } catch .tooMany {
            throw .tooSoon
        } catch {
            throw .failed(error)
        }
    }

    // MARK: transport

    private enum Method: String { case get = "GET", post = "POST", put = "PUT", delete = "DELETE" }

    private func send<Answer: Decodable>(_ method: Method, _ base: URL, _ path: String, body: (some Encodable)?,
                                         key: String? = nil) async throws(ServerFailure) -> Answer {
        let data = try await perform(method, base, path, body: body, key: key)
        // A 2xx the app cannot read: the server did answer, but the app must not treat it as paired.
        guard let answer = try? JSONDecoder().decode(Answer.self, from: data) else { throw .rejected(code: "unreadable_answer") }
        return answer
    }

    private func sendWithoutAnswer(_ method: Method, _ base: URL, _ path: String, body: (some Encodable)?,
                                   key: String) async throws(ServerFailure) {
        _ = try await perform(method, base, path, body: body, key: key)
    }

    private func perform(_ method: Method, _ base: URL, _ path: String, body: (some Encodable)?,
                         key: String?) async throws(ServerFailure) -> Data {
        var request = URLRequest(url: base.appending(path: path))
        request.httpMethod = method.rawValue
        if let key { request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization") }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try? JSONEncoder().encode(body)
        }
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw .retryLater
        }
        guard let http = response as? HTTPURLResponse else { throw .retryLater }
        switch http.statusCode {
        case 200..<300: return data
        case 401 where key != nil: throw .unauthorized
        case 429: throw .tooMany
        case 500...: throw .retryLater
        default: throw .rejected(code: (try? JSONDecoder().decode(ErrorBody.self, from: data))?.error ?? "http_\(http.statusCode)")
        }
    }

    private struct ErrorBody: Decodable { let error: String }
}
