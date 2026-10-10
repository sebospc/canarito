import Foundation

/// What the server's QR holds (docs/app-contract.md, section 1). Nothing here is a credential after
/// the pairing succeeds: the secret is single use.
public struct PairingInvite: Equatable, Sendable {
    public let server: URL
    public let secret: String
    public let relay: URL
    public let serverID: String
}

public enum PairingCodeError: Error, Equatable, Sendable {
    /// Not a canarito://pair link at all.
    case notCanarito
    /// `v` is not 1: this app cannot read it.
    case updateTheApp
    /// A parameter is missing or has the wrong shape.
    case malformed
    /// A plain http URL to a real host would send the position in the clear.
    case insecure
}

public enum PairingCode {
    /// `allowsLocalHTTP`: debug builds talk to a server on this Mac. Release builds never do.
    public static func parse(_ text: String, allowsLocalHTTP: Bool = false) throws(PairingCodeError) -> PairingInvite {
        guard let components = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              components.scheme?.lowercased() == "canarito", components.host?.lowercased() == "pair"
        else { throw .notCanarito }
        let query = Dictionary(components.queryItems?.compactMap { item in item.value.map { (item.name, $0) } } ?? [],
                               uniquingKeysWith: { first, _ in first })
        guard query["v"] == "1" else { throw query["v"] == nil ? .malformed : .updateTheApp }
        guard let secret = query["secret"], isHex(secret, length: 32),
              let serverID = query["sid"], isHex(serverID, length: 32),
              let serverText = query["server"], let relayText = query["relay"]
        else { throw .malformed }
        let server = try baseURL(serverText, allowsLocalHTTP: allowsLocalHTTP)
        let relay = try baseURL(relayText, allowsLocalHTTP: allowsLocalHTTP)
        return PairingInvite(server: server, secret: secret, relay: relay, serverID: serverID)
    }

    private static func baseURL(_ text: String, allowsLocalHTTP: Bool) throws(PairingCodeError) -> URL {
        guard let url = URL(string: text), let host = url.host(), !host.isEmpty else { throw .malformed }
        switch url.scheme?.lowercased() {
        case "https": break
        case "http" where allowsLocalHTTP && (host == "localhost" || host == "127.0.0.1"): break
        default: throw .insecure
        }
        // Calls append "/v1/...": a trailing slash would double it.
        let trimmed = url.absoluteString.hasSuffix("/") ? String(url.absoluteString.dropLast()) : url.absoluteString
        guard let base = URL(string: trimmed) else { throw .malformed }
        return base
    }

    private static func isHex(_ text: String, length: Int) -> Bool {
        text.count == length && text.allSatisfy(\.isHexDigit)
    }
}

/// The paired server, as the app remembers it. The device key is not here: it lives in the Keychain.
public struct Pairing: Codable, Equatable, Sendable {
    public let server: URL
    public let relay: URL
    public let serverID: String
    public let deviceID: String
    /// The receptor this phone belongs to, and the language of its alerts.
    public let receptor: String
    public let language: String

    public init(server: URL, relay: URL, serverID: String, deviceID: String, receptor: String, language: String) {
        self.server = server
        self.relay = relay
        self.serverID = serverID
        self.deviceID = deviceID
        self.receptor = receptor
        self.language = language
    }

    /// What the person recognizes: the server's host.
    public var serverHost: String { server.host() ?? server.absoluteString }
}
