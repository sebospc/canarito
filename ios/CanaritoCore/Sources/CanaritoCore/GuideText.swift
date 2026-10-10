/// Safety words quoted from UNGRD (Colombia), "Guía de preparativos ante sismo", 1.ª ed., noviembre
/// de 2024. Word for word, never shortened, adapted or translated: shown with `Text(verbatim:)`.
/// A new edition of the guide changes text, pictograms and citation together.
public enum GuideText {
    /// Three step headings joined (pp. 32, 33): protection comes before the posture on purpose.
    public static let protectiveLine = "¡Mantén la calma! Busca protección. Adopta una posición de seguridad."

    // After the shaking, in the guide's order (p. 38), plus the general aftershock line (p. 42).
    public static let health = "Una vez ha cesado el movimiento telúrico, tómate un momento para verificar tu estado de salud y para evaluar tu condición física."
    public static let evacuation = "Identifica y sigue la ruta de evacuación de forma segura, procurando cerrar los suministros de agua, luz y gas al salir."
    public static let aftershocks = "Ten en cuenta que se suelen presentar réplicas e incluso pueden ocurrir nuevos eventos que superen en magnitud al evento inicial."

    public static let source = "Fuente: UNGRD, Guía de preparativos ante sismo, 1.ª ed., noviembre de 2024."
    public static let sourceWithFollowAdvice = source + " Sigue al SGC y a la UNGRD."
}

/// The drawings that carry the guide's instructions. Each shows exactly what its quoted words say.
public enum Pictogram: String, CaseIterable, Sendable {
    case safetyPosition, health, evacuation, aftershocks

    public var guideText: String {
        switch self {
        case .safetyPosition: GuideText.protectiveLine
        case .health: GuideText.health
        case .evacuation: GuideText.evacuation
        case .aftershocks: GuideText.aftershocks
        }
    }
}
