import SwiftUI

/// The one button look: filled or outlined, 14 pt radius, a pressed state of its own. Reduce Motion
/// keeps the dimming and drops the scale.
struct CanaritoButtonStyle: ButtonStyle {
    enum Kind { case filled(background: Color, foreground: Color), outlined(Color) }
    let kind: Kind

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity, minHeight: 52)
            .padding(.horizontal, 16)
            .foregroundStyle(foreground)
            .background(background, in: .rect(cornerRadius: Brand.radius))
            .overlay { if case .outlined(let color) = kind { RoundedRectangle(cornerRadius: Brand.radius).stroke(color, lineWidth: 2) } }
            .opacity(!isEnabled ? 0.45 : configuration.isPressed ? 0.85 : 1)
            .scaleEffect(configuration.isPressed && isEnabled && !reduceMotion ? 0.96 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
            .contentShape(.rect(cornerRadius: Brand.radius))
    }

    private var foreground: Color {
        switch kind {
        case .filled(_, let foreground): foreground
        case .outlined(let color): color
        }
    }

    private var background: Color {
        if case .filled(let background, _) = kind { background } else { .clear }
    }
}

extension ButtonStyle where Self == CanaritoButtonStyle {
    static var canarito: CanaritoButtonStyle { .init(kind: .filled(background: Brand.accent, foreground: Brand.onAccent)) }
    static func canarito(background: Color, foreground: Color) -> CanaritoButtonStyle { .init(kind: .filled(background: background, foreground: foreground)) }
    static func canaritoOutlined(_ color: Color = Brand.text) -> CanaritoButtonStyle { .init(kind: .outlined(color)) }
}

/// A surface block: server line, warnings. Flat, tonal, never nested.
struct Card<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) { content }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Brand.surface, in: .rect(cornerRadius: Brand.radius))
    }
}

/// Reduce Motion replaces every slide with a cross-fade.
struct AppMotion {
    let reduceMotion: Bool
    var bottomEntrance: AnyTransition { reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity) }
    var stateChange: Animation? { reduceMotion ? nil : .smooth(duration: 0.4) }
}

extension EnvironmentValues {
    var appMotion: AppMotion { AppMotion(reduceMotion: accessibilityReduceMotion) }
}

/// Content that scrolls, with the buttons pinned below it. At accessibility text sizes the text is taller
/// than the screen and a pinned button would cut a line of it, so the buttons scroll with the text there.
/// Pinned buttons stay last in VoiceOver's reading order.
struct ScreenWithFooter<Content: View, Footer: View>: View {
    @ViewBuilder let content: Content
    @ViewBuilder let footer: Footer
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        if dynamicTypeSize.isAccessibilitySize {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    content
                    VStack(spacing: 10) { footer }.padding(.top, 16)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        } else {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) { content }.frame(maxWidth: .infinity, alignment: .leading)
                }
                .scrollBounceBehavior(.basedOnSize)
                VStack(spacing: 10) { footer }.fixedSize(horizontal: false, vertical: true).padding(.top, 10)
            }
        }
    }
}
