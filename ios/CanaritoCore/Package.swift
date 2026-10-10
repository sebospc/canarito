// swift-tools-version: 6.2
import PackageDescription

// Logic with no UI, tested with `swift test` on the Mac (no simulator needed).
// CanaritoCore is pure: values, rules and ports, Foundation only, no I/O. CanaritoAdapters does the
// I/O (HTTP, UserDefaults, Keychain, push payloads) and depends on the core, never the other way.
let package = Package(
    name: "CanaritoCore",
    defaultLocalization: "es",
    platforms: [.iOS(.v26), .macOS(.v26)],
    products: [.library(name: "CanaritoCore", targets: ["CanaritoCore", "CanaritoAdapters"])],
    targets: [
        .target(name: "CanaritoCore"),
        .target(name: "CanaritoAdapters", dependencies: ["CanaritoCore"]),
        .testTarget(name: "CanaritoCoreTests", dependencies: ["CanaritoCore", "CanaritoAdapters"]),
    ]
)
