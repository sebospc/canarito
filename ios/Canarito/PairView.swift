@preconcurrency import AVFoundation
import CanaritoCore
import SwiftUI

/// Scan the QR the server shows, or paste its link. Either way the person confirms the server's name
/// before the single-use secret is spent.
struct PairView: View {
    let model: AppModel
    @State private var pastedLink = ""
    @State private var problem: PairingProblem?
    @State private var isPairing = false
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Vincula tu servidor").displayTitle(size: 30, relativeTo: .title).accessibilityAddTraits(.isHeader).padding(.top, 32)
                if let invite = model.pendingInvite {
                    confirmation(invite)
                } else {
                    Text("En el computador del servidor ejecuta `canarito.py pair` y escanea el QR que aparece.").font(.body)
                    QRScanner(onCode: { problem = model.receive(link: $0) })
                        .frame(height: dynamicTypeSize.isAccessibilitySize ? 200 : 300)
                        .clipShape(.rect(cornerRadius: Brand.radius))
                        .accessibilityHidden(true)
                    Text("¿No puedes escanear? Pega el enlace que muestra el servidor.").font(.subheadline).foregroundStyle(Brand.textSecondary)
                    TextField("", text: $pastedLink, prompt: Text(verbatim: "canarito://pair?…").foregroundStyle(Brand.textSecondary))
                        .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                        .padding(14).frame(minHeight: 52).background(Brand.surface, in: .rect(cornerRadius: Brand.radius))
                        .accessibilityIdentifier("pairLink")
                    Button("Usar enlace") { problem = model.receive(link: pastedLink) }
                        .buttonStyle(.canaritoOutlined(Brand.accent))
                        .accessibilityIdentifier("useLink")
                }
                if let problem { problemText(problem) }
            }
            .padding(.horizontal, 24).padding(.bottom, 24)
        }
        .foregroundStyle(Brand.text)
    }

    private func confirmation(_ invite: PairingInvite) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Card {
                Text("¿Vincular este iPhone con este servidor?").font(.headline)
                Text(verbatim: invite.server.host() ?? invite.server.absoluteString).font(.title3.weight(.semibold))
                Text("Le enviará tu posición redondeada a 1 km cada vez que te muevas. Si no lo reconoces, cancela.")
                    .font(.subheadline).foregroundStyle(Brand.textSecondary)
            }
            Button {
                isPairing = true
                problem = nil
                Task {
                    problem = await model.pair(invite)
                    isPairing = false
                }
            } label: { Text(isPairing ? "Vinculando…" : "Vincular") }
                .buttonStyle(.canarito)
                .disabled(isPairing)
                .accessibilityIdentifier("pair")
            Button("Cancelar") { model.pendingInvite = nil; problem = nil }
                .buttonStyle(.canaritoOutlined())
                .disabled(isPairing)
        }
    }

    private func problemText(_ problem: PairingProblem) -> some View {
        Text(message(problem)).font(.subheadline.weight(.semibold)).foregroundStyle(Brand.coral)
            .accessibilityIdentifier("pairProblem")
            .onAppear { AccessibilityNotification.Announcement(String(localized: message(problem))).post() }
    }

    private func message(_ problem: PairingProblem) -> LocalizedStringResource {
        switch problem {
        case .notCanarito: "Ese enlace no es de Canarito."
        case .updateTheApp: "Este código es de una versión más nueva. Actualiza la app."
        case .insecure: "Ese servidor no usa una conexión segura (https). No lo vinculamos."
        case .malformed: "El código está incompleto. Genera otro en el servidor."
        case .badSecret: "El código ya se usó o venció. Genera otro con `canarito.py pair`."
        case .unreachable: "No llegamos al servidor. Revisa tu conexión y vuelve a intentarlo."
        case .noPushToken: "Este iPhone no pudo registrarse para recibir avisos. Revisa los permisos de notificaciones y tu conexión."
        case .other(let code): "El servidor rechazó la vinculación (\(code))."
        }
    }
}

/// Camera QR reader. Without a camera (Simulator) or without permission it shows why, and the pasted
/// link above stays available.
private struct QRScanner: View {
    let onCode: (String) -> Void
    @State private var access = AVCaptureDevice.authorizationStatus(for: .video)

    var body: some View {
        ZStack {
            Brand.surface
            if AVCaptureDevice.default(for: .video) == nil {
                note("camera.fill", "No hay cámara disponible.")
            } else if access == .denied || access == .restricted {
                note("camera.fill", "Canarito no tiene permiso para usar la cámara. Actívalo en Ajustes o pega el enlace.")
            } else {
                ScannerRepresentable(onCode: onCode)
            }
        }
        .task {
            if access == .notDetermined { _ = await AVCaptureDevice.requestAccess(for: .video); access = AVCaptureDevice.authorizationStatus(for: .video) }
        }
    }

    private func note(_ symbol: String, _ text: LocalizedStringKey) -> some View {
        VStack(spacing: 8) {
            Image(systemName: symbol).font(.title)
            Text(text).font(.subheadline).multilineTextAlignment(.center)
        }
        .foregroundStyle(Brand.textSecondary).padding()
    }
}

private struct ScannerRepresentable: UIViewControllerRepresentable {
    let onCode: (String) -> Void

    func makeUIViewController(context: Context) -> ScannerController {
        let controller = ScannerController()
        controller.onCode = onCode
        return controller
    }

    func updateUIViewController(_ controller: ScannerController, context: Context) {}
}

private final class ScannerController: UIViewController, @preconcurrency AVCaptureMetadataOutputObjectsDelegate {
    var onCode: (String) -> Void = { _ in }
    private let session = AVCaptureSession()
    private var preview: AVCaptureVideoPreviewLayer?
    private var lastCode: String?

    override func viewDidLoad() {
        super.viewDidLoad()
        guard let device = AVCaptureDevice.default(for: .video), let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else { return }
        session.addInput(input)
        let output = AVCaptureMetadataOutput()
        guard session.canAddOutput(output) else { return }
        session.addOutput(output)
        output.setMetadataObjectsDelegate(self, queue: .main)
        output.metadataObjectTypes = [.qr]
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        view.layer.addSublayer(layer)
        preview = layer
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        preview?.frame = view.bounds
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        let session = session
        DispatchQueue.global(qos: .userInitiated).async { session.startRunning() }
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        let session = session
        DispatchQueue.global(qos: .userInitiated).async { session.stopRunning() }
    }

    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput objects: [AVMetadataObject], from connection: AVCaptureConnection) {
        guard let code = (objects.first as? AVMetadataMachineReadableCodeObject)?.stringValue, code != lastCode else { return }
        lastCode = code
        onCode(code)
    }
}
