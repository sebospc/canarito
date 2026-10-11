import AVFoundation

/// Plays Canarito/Sounds/canarito-alert.caf (made by tools/make_alert_sound.py) on the alert screen.
/// The playback category ignores the silent switch on purpose: this is a warning, not a notification.
@MainActor
final class AlertSound {
    private var player: AVAudioPlayer?

    func start() {
        guard let url = Bundle.main.url(forResource: "canarito-alert", withExtension: "caf") else { return }
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        player = try? AVAudioPlayer(contentsOf: url)
        player?.play()
    }

    func stop() {
        player?.stop()
        player = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
