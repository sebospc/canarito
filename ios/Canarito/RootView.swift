import CanaritoCore
import SwiftUI

struct RootView: View {
    let model: AppModel
    @State private var showingSettings = false
    @Environment(\.appMotion) private var motion

    var body: some View {
        let state = Samples.state ?? model.state
        Group {
            if case .alert(let alert) = state {
                AlertView(alert: alert, now: model.now, playsSound: !model.alertCameFromTap, startsOnAfterScreen: Samples.startsOnAfterScreen, onClose: model.dismissAlert)
                    .transition(.opacity)
            } else if state == .notSetUp || Samples.showsSetup != nil {
                if Samples.showsSetup == .pair || (Samples.showsSetup == nil && model.hasSeenIntro) {
                    PairView(model: model)
                } else {
                    IntroView(model: model)
                }
            } else {
                HomeView(model: model, state: state, locationNotice: Samples.state != nil ? Samples.locationNotice : model.locationNotice,
                         showsNotificationsOff: Samples.state != nil ? Samples.showsNotificationsOff : model.notifications == .denied,
                         onShowSettings: { showingSettings = true })
            }
        }
        .animation(motion.stateChange, value: state)
        .sheet(isPresented: $showingSettings) { SettingsView(model: model) }
        // An alert must not open behind Settings: the test alert is sent from there, and with notifications
        // off there is no banner on top to see it by.
        .onChange(of: state) { _, newState in if case .alert = newState { showingSettings = false } }
        // A sheet presented in the first frame is dropped by SwiftUI: wait one beat (screenshots only).
        .task { if Samples.opensSettings { try? await Task.sleep(for: .milliseconds(600)); showingSettings = true } }
        .background(Brand.page.ignoresSafeArea())
        .preferredColorScheme(.dark)
    }
}
