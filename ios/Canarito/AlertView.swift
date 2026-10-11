import CanaritoCore
import CoreHaptics
import SwiftUI

/// In-app alert, once the person opens the app or taps the notification. The picture does the work,
/// the receptor's words confirm it. No bird, no map, no distance. What is shown follows `AlertScreen`;
/// this view only draws it.
struct AlertView: View {
    let alert: EarthquakeAlert
    let now: Date
    /// False when the person tapped the push: its own sound already rang, a second one would overlap it.
    let playsSound: Bool
    let onClose: () -> Void

    init(alert: EarthquakeAlert, now: Date, playsSound: Bool = true, startsOnAfterScreen: Bool = false, onClose: @escaping () -> Void) {
        self.alert = alert
        self.now = now
        self.playsSound = playsSound
        self.onClose = onClose
        _showingAfter = State(initialValue: startsOnAfterScreen)
    }

    @State private var haptics: CHHapticEngine?
    @State private var sound = AlertSound()
    @State private var showingAfter: Bool
    @ScaledMetric(relativeTo: .callout) private var pictogramSize = 84
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    private var screen: AlertScreen { AlertScreen(alert, now: now, locale: .current) }

    var body: some View {
        Group {
            if showingAfter {
                AfterView(onDone: onClose)
            } else {
                switch screen.kind {
                case .alert, .drill: alertScreen
                case .late: lateScreen
                case .test: testScreen
                }
            }
        }
        .accessibilityElement(children: .contain)
        .onAppear {
            UIApplication.shared.isIdleTimerDisabled = true
            // Late and test alerts: nothing a real, on-time alert does beyond the sound.
            if screen.kind == .alert || screen.kind == .drill {
                playHaptics()
                if playsSound { sound.start() }
            }
        }
        .onDisappear {
            UIApplication.shared.isIdleTimerDisabled = false
            haptics?.stop()
            sound.stop()
        }
    }

    // MARK: screens

    private func screenLayout<Content: View, Buttons: View>(background: Color, foreground: Color, scheme: ColorScheme, topPadding: CGFloat,
                                                            @ViewBuilder content: () -> Content,
                                                            @ViewBuilder buttons: () -> Buttons) -> some View {
        ScreenWithFooter {
            content().padding(.top, topPadding)
        } footer: {
            buttons()
        }
        .foregroundStyle(foreground)
        .padding(.horizontal, 24).padding(.bottom, 30)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(background.ignoresSafeArea())
        // The status bar follows the screen's own color, not the phone's setting.
        .preferredColorScheme(scheme)
    }

    private var alertScreen: some View {
        screenLayout(background: Brand.canary, foreground: Brand.onCanary, scheme: .light, topPadding: 50) {
            if screen.kind == .drill {
                Text("Simulacro: no es un sismo real").font(.subheadline.weight(.bold)).foregroundStyle(Brand.canary)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Brand.onCanary, in: .rect(cornerRadius: 10)).padding(.bottom, 10)
                    .accessibilityIdentifier("drillBand")
            }
            HStack(alignment: .firstTextBaseline) {
                Text(verbatim: screen.title).displayTitle(size: 20, relativeTo: .title3).accessibilityIdentifier("alertTitle")
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                if let magnitude = screen.magnitudeText {
                    Text(magnitude).displayTitle(size: 20, relativeTo: .title3)
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background(Brand.onCanary, in: .rect(cornerRadius: 10)).foregroundStyle(Brand.canary)
                        .accessibilityIdentifier("alertMagnitude")
                }
            }
            Text(verbatim: screen.body).font(.title3).padding(.top, 12).accessibilityIdentifier("alertBody")
            if screen.showsProtectiveLine {
                Self.pictogram(.safetyPosition, bleed: true).padding(.top, 22).padding(.bottom, 18)
                Text(verbatim: GuideText.protectiveLine).displayTitle(size: 20, relativeTo: .title3)
                    .accessibilityIdentifier("protectiveLine").padding(.bottom, 10)
            }
            elapsedLine.font(.body).foregroundStyle(Brand.onCanarySecondary).padding(.top, screen.showsProtectiveLine ? 0 : 18)
                .accessibilityIdentifier("alertElapsed")
        } buttons: {
            Button("Cerrar") { if screen.showsAfterSteps { showingAfter = true } else { onClose() } }
                .buttonStyle(.canarito(background: Brand.onCanary, foreground: Brand.canary))
                .accessibilityIdentifier("close")
        }
    }

    private var lateScreen: some View {
        screenLayout(background: Brand.page, foreground: Brand.text, scheme: .dark, topPadding: 56) {
            Label("Aviso tardío", systemImage: "clock")
                .font(.headline).foregroundStyle(Brand.coral).padding(.top, 22).padding(.bottom, 12)
                .accessibilityIdentifier("lateTag")
            elapsedLine.displayTitle(size: 30, relativeTo: .title).padding(.bottom, 8).accessibilityIdentifier("alertElapsed")
            Text(verbatim: screen.body).font(.body).foregroundStyle(Brand.textSecondary).padding(.bottom, 14)
            guideStep(.aftershocks)
        } buttons: {
            Button("Entendido", action: onClose)
                .buttonStyle(.canarito)
                .accessibilityIdentifier("close")
            Brand.sourceLine(GuideText.source).font(.caption).foregroundStyle(Brand.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var testScreen: some View {
        screenLayout(background: Brand.sand, foreground: Brand.onCanary, scheme: .light, topPadding: 50) {
            Text("Prueba: no hay sismo").font(.subheadline.weight(.bold)).foregroundStyle(Brand.onSand)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Brand.onCanary, in: .rect(cornerRadius: 10)).padding(.bottom, 10)
                .accessibilityIdentifier("testBand")
            Text("Aviso de prueba").displayTitle(size: 20, relativeTo: .title3).accessibilityIdentifier("alertTitle")
                .accessibilityAddTraits(.isHeader)
            Self.pictogram(.safetyPosition, bleed: true).padding(.top, 22).padding(.bottom, 18)
            Text(verbatim: GuideText.protectiveLine).displayTitle(size: 20, relativeTo: .title3).padding(.bottom, 10)
            Text("Así sonará un aviso de sismo. Esto es solo una prueba.").font(.body).foregroundStyle(Brand.onCanarySecondary)
        } buttons: {
            Button("Cerrar", action: onClose)
                .buttonStyle(.canarito(background: Brand.onCanary, foreground: Brand.canary))
                .accessibilityIdentifier("close")
        }
    }

    // MARK: pieces

    /// `bleed`: the drawing runs 8 pt past the text margin on each side, so the floor line is wider
    /// than the text column.
    static func pictogram(_ pictogram: Pictogram, bleed: Bool = false) -> some View {
        Brand.image(pictogram).resizable().scaledToFit()
            .frame(maxWidth: .infinity)
            .padding(.horizontal, bleed ? -8 : 0)
            .accessibilityLabel(Brand.description(pictogram))
            .accessibilityIdentifier("pictogram-\(pictogram.rawValue)")
    }

    private func guideStep(_ pictogram: Pictogram) -> some View {
        GuideRow(pictogram: pictogram, size: pictogramSize)
    }

    /// Ticks every second, so only this line redraws. Left out when the push has no origin time.
    @ViewBuilder
    private var elapsedLine: some View {
        if let occurredAt = alert.occurredAt {
            TimelineView(.periodic(from: now, by: 1)) { context in
                switch AlertScreen.elapsed(since: occurredAt, now: context.date) {
                case .seconds(let seconds): Text(screen.kind == .late ? "El sismo ocurrió hace \(seconds) s" : "Ocurrió hace \(seconds) s")
                case .minutes(let minutes): Text(screen.kind == .late ? "El sismo ocurrió hace \(minutes) min" : "Ocurrió hace \(minutes) min")
                }
            }
        }
    }

    /// A strong tap every second for the first 10 s, only while the app is in front.
    private func playHaptics() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics, let engine = try? CHHapticEngine() else { return }
        let taps = (0..<10).map { second in
            CHHapticEvent(eventType: .hapticTransient,
                          parameters: [CHHapticEventParameter(parameterID: .hapticIntensity, value: 1),
                                       CHHapticEventParameter(parameterID: .hapticSharpness, value: 0.8)],
                          relativeTime: TimeInterval(second))
        }
        guard let pattern = try? CHHapticPattern(events: taps, parameters: []),
              let player = try? engine.makePlayer(with: pattern) else { return }
        try? engine.start()
        try? player.start(atTime: 0)
        haptics = engine
    }
}

/// A pictogram and the guide's words beside it; stacked at accessibility sizes so the text keeps its width.
private struct GuideRow: View {
    let pictogram: Pictogram
    let size: CGFloat
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        let layout = dynamicTypeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 10))
                                                         : AnyLayout(HStackLayout(spacing: 14))
        layout {
            Brand.image(pictogram).resizable().scaledToFit().frame(width: size, height: size)
                .accessibilityLabel(Brand.description(pictogram))
            Text(verbatim: pictogram.guideText).font(.callout)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Brand.surface, in: .rect(cornerRadius: Brand.radius))
    }
}

/// What to do once the shaking has stopped, in the guide's order. No question: the answer would go nowhere.
struct AfterView: View {
    let onDone: () -> Void
    @ScaledMetric(relativeTo: .callout) private var pictogramSize = 84

    var body: some View {
        ScreenWithFooter {
            VStack(alignment: .leading, spacing: 10) {
                Text("Cuando pare el temblor").displayTitle(size: 30, relativeTo: .title).padding(.top, 4)
                    .accessibilityAddTraits(.isHeader).accessibilityIdentifier("afterTitle")
                ForEach(AlertScreen.afterSteps, id: \.self) { step in GuideRow(pictogram: step, size: pictogramSize) }
                Brand.sourceLine(GuideText.sourceWithFollowAdvice).font(.caption).foregroundStyle(Brand.textSecondary).padding(.top, 8)
            }
            .padding(.top, 56)
        } footer: {
            Button("Listo", action: onDone)
                .buttonStyle(.canarito)
                .accessibilityIdentifier("done")
        }
        .padding(.horizontal, 24).padding(.bottom, 30)
        .foregroundStyle(Brand.text)
        .background(Brand.page.ignoresSafeArea())
        .preferredColorScheme(.dark)
    }
}
