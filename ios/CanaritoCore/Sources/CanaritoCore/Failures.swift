import Foundation

public enum ServerFailure: Error, Equatable, Sendable {
    /// 4xx other than the two below: sending it again will not help. `code` is the server's `error`.
    case rejected(code: String)
    /// 401 `bad_key`: the server no longer knows this phone.
    case unauthorized
    /// No network or 5xx: try again later.
    case retryLater
    /// 429 (`rate_limited`, `slow_down`): try again later, with the latest data.
    case tooMany

}

public enum TestAlertFailure: Error, Equatable, Sendable {
    /// 429: one test per 10 minutes.
    case tooSoon
    case failed(ServerFailure)
}
