import CanaritoCore
import Foundation
import Security
import Synchronization

extension UserDefaults: KeyValueStore {
    public func set(data: Data?, forKey key: String) { set(data, forKey: key) }
    public func set(string: String?, forKey key: String) { set(string, forKey: key) }
}

/// For tests and previews.
public final class InMemoryStore: KeyValueStore, SecretStore {
    private let values = Mutex<[String: Data]>([:])

    public init() {}

    public func data(forKey key: String) -> Data? { values.withLock { $0[key] } }
    public func string(forKey key: String) -> String? { data(forKey: key).map { String(decoding: $0, as: UTF8.self) } }
    public func set(data: Data?, forKey key: String) { values.withLock { $0[key] = data } }
    public func set(string: String?, forKey key: String) { set(data: string.map { Data($0.utf8) }, forKey: key) }
    public func secret(forKey key: String) -> String? { string(forKey: key) }
    public func set(secret: String?, forKey key: String) { set(string: secret, forKey: key) }
}

/// The device key goes here and nowhere else. `AfterFirstUnlock`: a location wake-up with the phone
/// locked still has to send its position.
public struct KeychainSecretStore: SecretStore {
    private let service: String

    public init(service: String = "app.canarito.device") { self.service = service }

    public func secret(forKey key: String) -> String? {
        var query = baseQuery(key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess, let data = result as? Data else { return nil }
        return String(decoding: data, as: UTF8.self)
    }

    public func set(secret: String?, forKey key: String) {
        SecItemDelete(baseQuery(key) as CFDictionary)
        guard let secret else { return }
        var item = baseQuery(key)
        item[kSecValueData as String] = Data(secret.utf8)
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(item as CFDictionary, nil)
    }

    private func baseQuery(_ key: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: key]
    }
}
