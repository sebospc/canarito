import CanaritoCore
import Foundation

/// `-state <name>` on launch shows a sample screen, for Simulator screenshots and the audit. Debug
/// builds only: in Release every property is nil or false, so no sample can reach a person.
enum Samples {
    enum Setup { case intro, pair }

    #if DEBUG
    private static let name = UserDefaults.standard.string(forKey: "state")
    static var fakeGateway: Bool { UserDefaults.standard.bool(forKey: "fakeGateway") }
    static var fakeToken: Bool { UserDefaults.standard.bool(forKey: "fakeToken") }

    private static let sentAt = Date()
    /// The receptor writes the alert in its own language, so the sample follows the phone's.
    private static let isEnglish = Bundle.main.preferredLocalizations.first?.hasPrefix("en") == true
    private static let sampleAlert = EarthquakeAlert(id: "sample", title: isEnglish ? "Earthquake alert" : "Alerta de sismo",
                                                     body: isEnglish ? "Earthquake M5.4 near your area. Protect yourself now." : "Sismo M5.4 cerca de tu zona. Protégete ahora.",
                                                     magnitude: 5.4, occurredAt: sentAt - 3, sentAt: sentAt)
    private static func status(covered: Bool = true, receptorUp: Bool = true, relayOK: Bool = true) -> ServerStatus {
        ServerStatus(receptor: "casa", covered: covered, receptorUp: receptorUp, relayOK: relayOK, following: true)
    }

    static var state: HomeState? {
        switch name {
        case "covered", "travel-warning", "location-off": .covered
        case "not-covered": .notCovered
        case "checking": .checking
        case "alert", "after": .alert(sampleAlert)
        case "alert-late":
            .alert(EarthquakeAlert(id: "late", title: "Alerta de sismo", body: "Sismo M4.8 cerca de tu zona.", magnitude: 4.8,
                                   occurredAt: sentAt - 95, sentAt: sentAt, isLate: true))
        case "alert-test":
            .alert(EarthquakeAlert(id: "test", title: "Aviso de prueba", body: "Esto es una prueba.", sentAt: sentAt, isTest: true))
        case "alert-drill":
            .alert(EarthquakeAlert(id: "drill-1", title: "SIMULACRO: Alerta de sismo", body: "SIMULACRO: sismo M5.4 cerca de tu zona. Protégete ahora.",
                                   magnitude: 5.4, sentAt: sentAt, isDrill: true))
        case "unreachable": .error(.serverUnreachable)
        case "relay-down": .error(.relayDown)
        case "receptor-down": .error(.receptorDown)
        case "notifications-off": .error(.notificationsOff)
        case "time-sensitive-off": .error(.timeSensitiveOff)
        case "not-registered": .error(.notRegistered)
        case "removed": .error(.removedByServer)
        default: nil
        }
    }

    static var showsSetup: Setup? {
        switch name {
        case "intro": .intro
        case "pair": .pair
        default: nil
        }
    }

    static var startsOnAfterScreen: Bool { name == "after" }
    static var locationNotice: LocationNotice? {
        switch name {
        case "travel-warning": .travel
        case "location-off": .off
        default: nil
        }
    }
    static var showsNotificationsOff: Bool { name == "notifications-off" }
    static var opensSettings: Bool { UserDefaults.standard.string(forKey: "sheet") == "settings" }
    static var pairing: Pairing? {
        name == nil ? nil : Pairing(server: URL(string: "https://canarito.example.org")!, relay: URL(string: "https://relay.example.org")!,
                                    serverID: "a1", deviceID: "d_1", receptor: "casa", language: "es")
    }
    #else
    static let fakeGateway = false
    static let fakeToken = false
    static let state: HomeState? = nil
    static let showsSetup: Setup? = nil
    static let startsOnAfterScreen = false
    static let locationNotice: LocationNotice? = nil
    static let showsNotificationsOff = false
    static let opensSettings = false
    static let pairing: Pairing? = nil
    #endif
}
