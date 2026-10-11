import Foundation

public enum Polling {
    /// Checks `value` every `interval` until it returns something, `giveUp` says stop, or `attempts` run out.
    /// Used for the APNs token, which iOS delivers through a delegate callback at its own pace.
    @MainActor
    public static func wait<Value>(attempts: Int, interval: Duration, giveUp: () -> Bool = { false },
                                   value: () -> Value?) async -> Value? {
        for attempt in 0..<attempts {
            if let found = value() { return found }
            if giveUp() || attempt == attempts - 1 { return nil }
            try? await Task.sleep(for: interval)
        }
        return nil
    }
}
