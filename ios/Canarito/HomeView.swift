import CanaritoCore
import SwiftUI

/// One symbol, one line of state, one line of detail, a button only when the person must act.
struct HomeView: View {
    let model: AppModel
    let state: HomeState
    let showsTravelWarning: Bool
    let onShowSettings: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.appMotion) private var motion
    @Environment(\.openURL) private var openURL
    @ScaledMetric(relativeTo: .largeTitle) private var symbolSize = 64
    @ScaledMetric(relativeTo: .headline) private var birdWidth = 26

    var body: some View {
        let look = Look(state, receptor: Samples.state != nil ? "casa" : model.pairing?.receptor)
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 0) {
                    header
                    VStack(spacing: 16) {
                        Image(systemName: look.symbol)
                            .font(.system(size: symbolSize, weight: .semibold))
                            .foregroundStyle(look.tint)
                            .contentTransition(.symbolEffect(.replace))
                            // Covered: one slow pulse says "alive". Nothing else moves.
                            .symbolEffect(.pulse, options: .repeat(.periodic(delay: 2.5)).speed(0.5), isActive: look.pulses && !reduceMotion)
                            .padding(.bottom, 16)
                            .accessibilityHidden(true)
                        VStack(spacing: 8) {
                            Text(look.title).displayTitle(size: 28, relativeTo: .title).accessibilityAddTraits(.isHeader)
                            if let detail = look.detail { Text(detail).font(.body) }
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("state")
                        if let action = look.action, dynamicTypeSize.isAccessibilitySize { actionButton(action).padding(.top, 8) }
                        if let pairing = model.pairing ?? Samples.pairing { serverCard(pairing) }
                        if showsTravelWarning { travelWarning }
                    }
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity, minHeight: 480)
                }
                .padding(.horizontal, 28)
            }
            .scrollBounceBehavior(.basedOnSize)
            // At accessibility sizes the text is taller than the screen: a pinned button would cut a
            // line of it, so the button scrolls with the text there.
            if let action = look.action, !dynamicTypeSize.isAccessibilitySize {
                actionButton(action).padding(.horizontal, 28).padding(.bottom, 12).transition(motion.bottomEntrance)
            }
        }
        .foregroundStyle(Brand.text)
        .sensoryFeedback(trigger: look.pulses) { _, covered in covered ? .success : .warning }
        .onChange(of: look.title) { _, title in
            AccessibilityNotification.Announcement("\(title). \(look.detail ?? "")").post()
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image("Bird").resizable().scaledToFit().frame(width: birdWidth, height: birdWidth * 0.77)
                .foregroundStyle(Brand.accent).accessibilityHidden(true)
            Text(verbatim: "Canarito").displayTitle(size: 20, relativeTo: .headline).lineLimit(1).minimumScaleFactor(0.6)
                .accessibilityAddTraits(.isHeader)
            Spacer()
            Button(action: onShowSettings) {
                Image(systemName: "gearshape").font(.title3).frame(width: 44, height: 44)
            }
            .accessibilityLabel("Ajustes")
            .accessibilityIdentifier("settings")
        }
        .padding(.top, 8)
    }

    private func serverCard(_ pairing: Pairing) -> some View {
        Button(action: onShowSettings) {
            Card {
                Text("Servidor").font(.footnote).foregroundStyle(Brand.textSecondary)
                Text(verbatim: pairing.serverHost).font(.headline)
                Text("Receptor: \(pairing.receptor)").font(.subheadline).foregroundStyle(Brand.textSecondary)
            }
            .multilineTextAlignment(.leading)
        }
        .buttonStyle(.plain)
        .padding(.top, 16)
        .accessibilityHint("Abre los ajustes del servidor")
        .accessibilityIdentifier("serverCard")
    }

    private var travelWarning: some View {
        Card {
            Text("Si viajas, Canarito no lo sabe").font(.headline)
            Text("Sin ubicación «Siempre», tu servidor sigue la zona donde abriste la app por última vez. Si cambias de ciudad, podrías no recibir los avisos de tu zona.")
                .font(.subheadline)
            Button("Permitir ubicación «Siempre»") { openSettings() }
                .buttonStyle(.canaritoOutlined(Brand.accent))
                .padding(.top, 4)
                .accessibilityIdentifier("travelWarningButton")
        }
        .multilineTextAlignment(.leading)
        .padding(.top, 8)
    }

    private func actionButton(_ action: Look.Action) -> some View {
        Button {
            switch action.kind {
            case .openSettings: openSettings()
            case .retry: Task { await model.refresh() }
            case .pairAgain: Task { _ = await model.unpair(force: true) }
            }
        } label: { Text(action.title) }
            .buttonStyle(.canarito)
            .accessibilityIdentifier("action")
    }

    private func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
    }
}

/// Words and symbol for each state. Tú, per the brand; no numbers on screen.
private struct Look {
    struct Action {
        enum Kind { case openSettings, retry, pairAgain }
        let kind: Kind
        let title: LocalizedStringKey
    }

    var symbol: String
    var tint: Color
    var title: LocalizedStringKey
    var detail: LocalizedStringKey?
    var action: Action?
    var pulses = false

    init(_ state: HomeState, receptor: String?) {
        switch state {
        case .notSetUp, .checking:
            self.init(symbol: "arrow.triangle.2.circlepath", tint: Brand.textSecondary, title: "Comprobando",
                      detail: "Hablando con tu servidor.")
        case .covered:
            self.init(symbol: "checkmark.shield.fill", tint: Brand.accent, title: "Avisos activos",
                      detail: "Te cubre el receptor «\(receptor ?? "")».", pulses: true)
        case .notCovered:
            self.init(symbol: "shield.slash", tint: Brand.canary, title: "Tu zona no tiene cobertura",
                      detail: "Ningún receptor de tu servidor te cubre ahora. No te llegarán avisos.")
        case .alert:
            // Shown by AlertView; kept for completeness.
            self.init(symbol: "exclamationmark.triangle.fill", tint: Brand.coral, title: "Aviso de sismo")
        case .error(.notificationsOff):
            self.init(symbol: "bell.slash", tint: Brand.canary, title: "Notificaciones apagadas",
                      detail: "La app funciona, pero tu iPhone no sonará si hay un sismo. Puedes activarlas cuando quieras.",
                      action: .init(kind: .openSettings, title: "Activar notificaciones"))
        case .error(.timeSensitiveOff):
            self.init(symbol: "exclamationmark.triangle.fill", tint: Brand.canary, title: "Los avisos pueden no sonar",
                      detail: "Con un modo de Concentración activo, el aviso puede llegar en silencio.",
                      action: .init(kind: .openSettings, title: "Abrir Ajustes"))
        case .error(.locationOff):
            self.init(symbol: "location.slash.fill", tint: Brand.coral, title: "Falta tu ubicación",
                      detail: "Tu servidor la usa, redondeada a 1 km, para poner el receptor donde estás. Sin ella no sabemos si te cubre.",
                      action: .init(kind: .openSettings, title: "Abrir Ajustes"))
        case .error(.notRegistered):
            self.init(symbol: "wifi.exclamationmark", tint: Brand.coral, title: "Tu iPhone aún no está registrado",
                      detail: "Sin registro no te llegan avisos. Revisa tu conexión.", action: .init(kind: .retry, title: "Reintentar"))
        case .error(.serverUnreachable):
            self.init(symbol: "antenna.radiowaves.left.and.right.slash", tint: Brand.coral, title: "No llegamos a tu servidor",
                      detail: "Revisa tu conexión y que el servidor esté encendido. Mientras tanto no sabemos si te llegarán avisos.",
                      action: .init(kind: .retry, title: "Reintentar"))
        case .error(.receptorDown):
            self.init(symbol: "antenna.radiowaves.left.and.right.slash", tint: Brand.coral, title: "Tu receptor no responde",
                      detail: "El receptor que te cubre está apagado. Avisa a quien administra el servidor.",
                      action: .init(kind: .retry, title: "Reintentar"))
        case .error(.relayDown):
            self.init(symbol: "bell.slash.fill", tint: Brand.coral, title: "Los avisos pueden no llegar",
                      detail: "Tu servidor no logra enviar avisos a tu iPhone. Avisa a quien lo administra.",
                      action: .init(kind: .retry, title: "Reintentar"))
        case .error(.removedByServer):
            self.init(symbol: "link.badge.plus", tint: Brand.coral, title: "Tu servidor ya no te conoce",
                      detail: "Vincula tu iPhone otra vez con un código nuevo.", action: .init(kind: .pairAgain, title: "Vincular de nuevo"))
        }
    }

    private init(symbol: String, tint: Color, title: LocalizedStringKey, detail: LocalizedStringKey? = nil, action: Action? = nil,
                 pulses: Bool = false) {
        self.symbol = symbol
        self.tint = tint
        self.title = title
        self.detail = detail
        self.action = action
        self.pulses = pulses
    }
}
