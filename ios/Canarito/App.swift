import BackgroundTasks
import CanaritoAdapters
import CanaritoCore
import SwiftUI
import UserNotifications

@main
struct CanaritoApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView(model: appDelegate.model)
                // The camera can open a pairing QR straight into the app.
                .onOpenURL { _ = appDelegate.model.receive(link: $0.absoluteString) }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { appDelegate.model.becameActive() } else { appDelegate.model.resignedActive() }
        }
    }
}

/// Owns the model so it exists on background launches too (location wake-ups have no scene).
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    @MainActor lazy var model = AppModel(service: Self.makeService(), store: UserDefaults.standard, secrets: Self.makeSecrets())

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        BGTaskScheduler.shared.register(forTaskWithIdentifier: AppModel.refreshTaskIdentifier, using: nil) { task in
            let work = Task { @MainActor in
                await self.model.backgroundRefresh()
                AppModel.scheduleBackgroundRefresh()
                task.setTaskCompleted(success: true)
            }
            task.expirationHandler = { work.cancel() }
        }
        AppModel.scheduleBackgroundRefresh()
        MainActor.assumeIsolated {
            model.launched()
            #if DEBUG
            if Samples.fakeToken { model.tokenArrived(Data(repeating: 0xAB, count: 32)) }
            #endif
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        MainActor.assumeIsolated { model.tokenArrived(deviceToken) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        MainActor.assumeIsolated { model.tokenFailed(error) }
    }

    /// In the foreground the app shows the alert screen itself; a repeat of the same alert id stays silent.
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async
        -> UNNotificationPresentationOptions {
        guard let alert = EarthquakeAlert(userInfo: notification.request.content.userInfo) else { return [.banner, .list, .sound] }
        let isNew = await MainActor.run { model.received(alert) }
        return isNew ? [.banner, .list, .sound] : []
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        guard let alert = EarthquakeAlert(userInfo: response.notification.request.content.userInfo) else { return }
        _ = await MainActor.run { model.received(alert, fromTap: true) }
    }

    private static func makeService() -> any CanaritoService {
        #if DEBUG
        if Samples.fakeGateway { return ServerClient(session: FakeGateway.makeSession()) }
        #endif
        return ServerClient()
    }

    private static func makeSecrets() -> any SecretStore {
        #if DEBUG
        if Samples.fakeGateway { return InMemoryStore() }
        #endif
        return KeychainSecretStore()
    }
}
