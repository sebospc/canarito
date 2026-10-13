import SwiftUI

/// First run: what the app does and why it asks, then the two system prompts. Nothing is asked before
/// the person has read why.
struct IntroView: View {
    let model: AppModel
    @State private var isAsking = false
    @Environment(\.openURL) private var openURL
    @ScaledMetric(relativeTo: .body) private var iconWidth = 34

    var body: some View {
        ScreenWithFooter {
            VStack(alignment: .leading, spacing: 24) {
                Text("Avisos de sismo de tu servidor, en tu iPhone.").displayTitle(size: 30, relativeTo: .title)
                    .accessibilityAddTraits(.isHeader).padding(.top, 32)
                row("bell.badge.fill", "Suena cuando hay un sismo",
                    "Cuando el receptor de tu servidor recibe una alerta temprana de sismo, tu iPhone suena.")
                row("location.fill", "Pide tu ubicación «Siempre»",
                    "Para que el receptor esté donde estás, Canarito envía a tu servidor tu posición redondeada a 1 km, solo cuando te mueves. Tu posición exacta no sale del iPhone.")
                row("person.crop.circle.badge.xmark", "Sin cuentas",
                    "Solo hablas con el servidor al que te vincules. Sin registro, sin correo, sin anuncios.")
                Text("Canarito no es un sistema oficial y puede fallar o llegar tarde. Si sientes un sismo, protégete aunque no suene nada.")
                    .font(.subheadline).foregroundStyle(Brand.textSecondary)
                Button { if let url = URL(string: Self.privacyLink) { openURL(url) } } label: {
                    Text("Cómo se usan tus datos").font(.subheadline).frame(minHeight: 44)
                }
                .foregroundStyle(Brand.accent)
            }
        } footer: {
            Button {
                isAsking = true
                Task { await model.askPermissions() }
            } label: { Text("Continuar") }
                .buttonStyle(.canarito)
                .disabled(isAsking)
                .accessibilityIdentifier("continue")
        }
        .padding(.horizontal, 24).padding(.bottom, 12)
        .foregroundStyle(Brand.text)
    }

    static let privacyLink = "https://canarito.app/privacy"

    private func row(_ symbol: String, _ title: LocalizedStringKey, _ text: LocalizedStringKey) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 14) {
            Image(systemName: symbol).font(.title3).foregroundStyle(Brand.accent).frame(width: iconWidth).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline)
                Text(text).font(.body).foregroundStyle(Brand.textSecondary)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
