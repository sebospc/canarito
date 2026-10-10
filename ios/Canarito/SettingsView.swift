import CanaritoCore
import SwiftUI

/// The server, what is sent to it, a test alert and the way out.
struct SettingsView: View {
    let model: AppModel
    @State private var confirmingUnpair = false
    @State private var unpairFailed = false
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            List {
                if let pairing = model.pairing ?? Samples.pairing {
                    Section {
                        LabeledContent("Servidor") { Text(verbatim: pairing.serverHost) }
                        LabeledContent("Receptor") { Text(verbatim: pairing.receptor) }
                        if case .ok(let status, _) = model.status {
                            LabeledContent("Estado") { Text(status.covered ? "Te cubre" : "Sin cobertura") }
                        }
                    } header: { Text("Tu servidor") }
                    .listRowBackground(Brand.surface)
                }
                Section {
                    Text("A tu servidor: tu posición redondeada a 1 km, cuando te mueves, y un identificador de tu iPhone que solo el relé de Canarito puede abrir para enviarte el aviso.")
                    Text("Al relé: el aviso pasa por él hacia Apple. No guarda nada.")
                    Text("El responsable de lo que guarda el servidor es quien lo administra.")
                } header: { Text("Qué se envía") }
                .listRowBackground(Brand.surface)
                Section {
                    Button { Task { await model.sendTestAlert() } } label: { Label("Enviar aviso de prueba", systemImage: "speaker.wave.2.fill") }
                        .disabled(model.testAlertStatus == .sending)
                        .accessibilityIdentifier("testAlert")
                    if let line = testLine { Text(line).font(.footnote).accessibilityIdentifier("testAlertStatus") }
                } footer: { Text("Te llega un aviso de prueba para que escuches cómo suena.") }
                .listRowBackground(Brand.surface)
                Section {
                    Button("Cómo se usan tus datos") { if let url = URL(string: IntroView.privacyLink) { openURL(url) } }
                    Button("Desvincular este iPhone", role: .destructive) { confirmingUnpair = true }
                        .accessibilityIdentifier("unpair")
                        .confirmationDialog("¿Desvincular este iPhone?", isPresented: $confirmingUnpair, titleVisibility: .visible) {
                            Button("Desvincular", role: .destructive) {
                                Task {
                                    if await model.unpair(force: false) { dismiss() } else { unpairFailed = true }
                                }
                            }
                        } message: { Text("Dejarás de recibir avisos de este servidor.") }
                        .confirmationDialog("No pudimos avisar al servidor", isPresented: $unpairFailed, titleVisibility: .visible) {
                            Button("Desvincular de todos modos", role: .destructive) {
                                Task { _ = await model.unpair(force: true); dismiss() }
                            }
                        } message: { Text("Si desvinculas ahora, el servidor seguirá creyendo que este iPhone existe hasta que su administrador lo quite.") }
                } footer: {
                    Text("Esta app no es un sistema oficial. Puede fallar o llegar tarde, y no reemplaza las indicaciones de las autoridades.")
                }
                .listRowBackground(Brand.surface)
            }
            .navigationTitle("Ajustes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Listo") { dismiss() } } }
            .toolbarBackground(Brand.page, for: .navigationBar)
            .toolbarBackgroundVisibility(.visible, for: .navigationBar)
            .scrollContentBackground(.hidden)
            .background(Brand.page.ignoresSafeArea())
            .tint(Brand.accent)
        }
        .preferredColorScheme(.dark)
    }

    private var testLine: LocalizedStringKey? {
        switch model.testAlertStatus {
        case .idle, .sending: nil
        case .sent: "Enviado. Debería sonar en unos segundos."
        case .tooSoon: "Espera 10 minutos antes de pedir otra prueba."
        case .failed: "No se pudo enviar. Revisa tu servidor."
        }
    }
}
