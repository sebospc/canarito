import CanaritoCore
import Foundation

extension EarthquakeAlert {
    /// Reads the APNs payload of docs/app-contract.md, section 4. nil for anything that is not an
    /// alert: no `canarito.id`, or no text to show.
    public init?(userInfo: [AnyHashable: Any]) {
        guard let canarito = userInfo["canarito"] as? [String: Any], let id = canarito["id"] as? String,
              let alert = (userInfo["aps"] as? [String: Any])?["alert"] as? [String: Any],
              let body = alert["body"] as? String, !body.isEmpty
        else { return nil }
        let epoch = { (key: String) in (canarito[key] as? NSNumber).map { Date(timeIntervalSince1970: $0.doubleValue) } }
        self.init(id: id, title: alert["title"] as? String ?? "", body: body,
                  magnitude: (canarito["magnitude"] as? NSNumber)?.doubleValue,
                  occurredAt: epoch("occurred_at"), sentAt: epoch("sent_at") ?? Date(),
                  isLate: (canarito["late"] as? NSNumber)?.boolValue,
                  isTest: (canarito["test"] as? NSNumber)?.boolValue ?? false,
                  isDrill: (canarito["drill"] as? NSNumber)?.boolValue ?? false)
    }
}
