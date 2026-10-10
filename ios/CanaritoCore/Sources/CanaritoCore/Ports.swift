import Foundation

public enum PushEnvironment: String, Codable, Sendable {
    case production, sandbox
}

public struct PairResult: Equatable, Sendable {
    public let deviceID: String
    public let deviceKey: String
    public let receptor: String
    public let language: String

    public init(deviceID: String, deviceKey: String, receptor: String, language: String) {
        self.deviceID = deviceID
        self.deviceKey = deviceKey
        self.receptor = receptor
        self.language = language
    }
}

/// `GET /v1/status`: what the server knows about this phone's coverage right now.
public struct ServerStatus: Equatable, Sendable {
    public let receptor: String
    /// Some receptor covers this phone's position.
    public let covered: Bool
    public let receptorUp: Bool
    /// The push relay answered the server's last push.
    public let relayOK: Bool
    /// The receptor moves with the phone, so the phone's position matters.
    public let following: Bool

    public init(receptor: String, covered: Bool, receptorUp: Bool, relayOK: Bool, following: Bool) {
        self.receptor = receptor
        self.covered = covered
        self.receptorUp = receptorUp
        self.relayOK = relayOK
        self.following = following
    }
}

/// What the app asks of the relay and of its server (docs/app-contract.md). One port, one adapter
/// (`ServerClient`), and a fake in the app for the Simulator and the UI tests.
public protocol CanaritoService: Sendable {
    /// 2a. The relay seals the APNs token into a handle bound to this server.
    func handle(relay: URL, serverID: String, apnsToken: String, environment: PushEnvironment) async throws(ServerFailure) -> String
    /// 2b.
    func pair(invite: PairingInvite, handle: String, deviceName: String) async throws(ServerFailure) -> PairResult
    /// 2c. A new APNs token gave a new handle.
    func updateHandle(_ handle: String, pairing: Pairing, deviceKey: String) async throws(ServerFailure)
    func removeDevice(pairing: Pairing, deviceKey: String) async throws(ServerFailure)
    /// 3.
    func sendPosition(_ position: RoundedPosition, pairing: Pairing, deviceKey: String) async throws(ServerFailure)
    func status(pairing: Pairing, deviceKey: String) async throws(ServerFailure) -> ServerStatus
    func requestTestAlert(pairing: Pairing, deviceKey: String) async throws(TestAlertFailure)
}

/// Small local state. Same three value kinds as UserDefaults.
public protocol KeyValueStore: Sendable {
    func data(forKey key: String) -> Data?
    func string(forKey key: String) -> String?
    func set(data: Data?, forKey key: String)
    func set(string: String?, forKey key: String)
}

/// The device key: the app's only credential for the server. The Keychain in the app.
public protocol SecretStore: Sendable {
    func secret(forKey key: String) -> String?
    func set(secret: String?, forKey key: String)
}
