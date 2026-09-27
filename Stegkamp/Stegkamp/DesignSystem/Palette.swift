import SwiftUI
import UIKit

/// Stegkamp's colors. Every foreground color meets WCAG AA (4.5:1) against the system backgrounds
/// it is used on; `PaletteContrastTests` guards this.
enum Palette {
    /// The UIKit colors behind the foreground tokens, for contrast checks and UIKit APIs.
    enum UI {
        static let accent = UIColor(light: 0xC8341A, dark: 0xFF6B47)
        static let success = UIColor(light: 0x087A58, dark: 0x34D6A4)
        static let gold = UIColor(light: 0x8A5F00, dark: 0xFFC23D)
        static let buttonTop = UIColor(hex: 0xD63A1B)
        static let buttonBottom = UIColor(hex: 0xC2185B)
    }

    /// "Glöd" – buttons, links and highlights.
    static let accent = Color(uiColor: UI.accent)
    /// Start and end of the brand gradient, used for large decorative surfaces only (never for text).
    static let glowStart = Color(hex: 0xFF5A36)
    static let glowEnd = Color(hex: 0xFF2D87)
    /// Fill behind white button labels; both stops keep white text above 4.5:1.
    static let buttonTop = Color(uiColor: UI.buttonTop)
    static let buttonBottom = Color(uiColor: UI.buttonBottom)

    /// "Mynta" – goal reached, payment received, money coming your way.
    static let success = Color(uiColor: UI.success)
    static let gold = Color(uiColor: UI.gold)
    /// Silver and bronze are decorative (medals, podium) and never carry text.
    static let silver = Color(light: 0x8A94A3, dark: 0xC9D1DC)
    static let bronze = Color(light: 0xA15C2E, dark: 0xD98E5A)
    /// Deep navy behind share cards and the app icon.
    static let midnight = Color(hex: 0x0E1330)

    static let background = Color(uiColor: .systemGroupedBackground)
    static let surface = Color(uiColor: .secondarySystemGroupedBackground)
    static let raisedSurface = Color(uiColor: .tertiarySystemGroupedBackground)
    static let ringTrack = Color(light: 0xFBE3DC, dark: 0x3A1F1A)

    static var glowGradient: LinearGradient {
        LinearGradient(colors: [glowStart, glowEnd], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    static var buttonGradient: LinearGradient {
        LinearGradient(colors: [buttonTop, buttonBottom], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    /// Medal color for a final placing, or `nil` outside the podium.
    static func medal(forRank rank: Int) -> Color? {
        switch rank {
        case 1: gold
        case 2: silver
        case 3: bronze
        default: nil
        }
    }
}

extension UIColor {
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: alpha
        )
    }

    convenience init(light: UInt32, dark: UInt32) {
        self.init { traits in
            traits.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light)
        }
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(uiColor: UIColor(hex: hex))
    }

    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor(light: light, dark: dark))
    }
}
