import CanaritoCore
import SwiftUI
import UIKit

/// Canarito palette (DESIGN.md). Night teal for the app, canary yellow only for the alert. The bird is
/// the app icon and the small mark on the home screen: never on an alert, late or after screen.
enum Brand {
    static let canary = Color(hex: 0xF5C842)
    static let onCanary = Color(hex: 0x1E1700)
    static let onCanarySecondary = Color(hex: 0x4A3B00)
    static let sand = Color(hex: 0xD9D4C4)
    static let coral = Color(hex: 0xF08A6E)
    static let page = Color(hex: 0x0E1517)
    static let surface = Color(hex: 0x172226)
    static let text = Color(hex: 0xE4ECEC)
    static let textSecondary = Color(hex: 0x9DB0B2)
    static let accent = Color(hex: 0x56C2B6)
    static let onAccent = Color(hex: 0x062421)
    static let outline = Color(hex: 0x3A474B)
    /// Ink on the sand test screen band.
    static let onSand = Color(hex: 0xF4F4F2)

    /// One radius for cards and buttons.
    static let radius: CGFloat = 14

    static func image(_ pictogram: Pictogram) -> Image {
        switch pictogram {
        case .safetyPosition: Image("PictoPosition")
        case .health: Image("PictoHealth")
        case .evacuation: Image("PictoEvacuation")
        case .aftershocks: Image("PictoAftershocks")
        }
    }

    /// What VoiceOver says for each drawing: exactly what its quoted words show.
    static func description(_ pictogram: Pictogram) -> LocalizedStringKey {
        switch pictogram {
        case .safetyPosition: "Persona acurrucada de lado en el suelo, bajo una mesa firme, con las manos cruzadas detrás de la cabeza"
        case .health: "Persona y cruz médica"
        case .evacuation: "Persona caminando hacia una puerta; agua, luz y gas cerrados"
        case .aftershocks: "Casa con líneas de movimiento: réplicas"
        }
    }

    /// "Fuente: UNGRD, *Guía de preparativos ante sismo*, ..." with the guide's title in italics.
    static func sourceLine(_ source: String) -> Text {
        var text = AttributedString(source)
        if let title = text.range(of: "Guía de preparativos ante sismo") { text[title].font = .caption.italic() }
        return Text(text)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double(hex >> 16 & 0xFF) / 255, green: Double(hex >> 8 & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

/// Bricolage Grotesque for display titles only; body text, buttons and captions stay in the system font.
/// A variable font: weight 800, width 100 and the optical size set to the point size (clamped to 12-96),
/// as the landing does. Without the file, titles fall back to the system rounded heavy.
enum DisplayFont {
    private static let weightAxis = 2003265652, widthAxis = 2003072104, opticalSizeAxis = 1869640570  // 'wght', 'wdth', 'opsz'
    static let postScriptName = "BricolageGrotesque-96ptExtraBold"

    static func font(size: CGFloat) -> Font {
        guard let base = UIFont(name: postScriptName, size: size) else {
            return .system(size: size, weight: .heavy, design: .rounded)
        }
        let variation: [Int: CGFloat] = [weightAxis: 800, widthAxis: 100, opticalSizeAxis: min(max(size, 12), 96)]
        let descriptor = base.fontDescriptor.addingAttributes([UIFontDescriptor.AttributeName(rawValue: kCTFontVariationAttribute as String): variation])
        return Font(UIFont(descriptor: descriptor, size: size))
    }
}

/// `@ScaledMetric` scaling, so the title follows Dynamic Type and redraws when it changes.
private struct DisplayTitle: ViewModifier {
    @ScaledMetric private var size: CGFloat

    init(size: CGFloat, relativeTo style: Font.TextStyle) {
        _size = ScaledMetric(wrappedValue: size, relativeTo: style)
    }

    func body(content: Content) -> some View { content.font(DisplayFont.font(size: size)) }
}

extension View {
    func displayTitle(size: CGFloat, relativeTo style: Font.TextStyle = .title) -> some View {
        modifier(DisplayTitle(size: size, relativeTo: style))
    }
}
