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
                HomeView(model: model, state: state, showsTravelWarning: Samples.state != nil ? Samples.showsTravelWarning : model.showsTravelWarning,
                         onShowSettings: { showingSettings = true })
            }
        }
        .animation(motion.stateChange, value: state)
        .sheet(isPresented: $showingSettings) { SettingsView(model: model) }
        // A sheet presented in the first frame is dropped by SwiftUI: wait one beat (screenshots only).
        .task { if Samples.opensSettings { try? await Task.sleep(for: .milliseconds(600)); showingSettings = true } }
        .background(Brand.page.ignoresSafeArea())
        .preferredColorScheme(.dark)
    }
}
