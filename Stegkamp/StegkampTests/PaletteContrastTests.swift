import Testing
import UIKit
@testable import Stegkamp

/// Guards WCAG AA (4.5:1) for every palette color that is used for text or icons.
@Suite("Palette contrast")
@MainActor
struct PaletteContrastTests {
    private static let minimum = 4.5

    private static let foregrounds: [(name: String, color: UIColor)] = [
        ("accent", Palette.UI.accent),
        ("success", Palette.UI.success),
        ("gold", Palette.UI.gold)
    ]

    private static let backgrounds: [(name: String, color: UIColor)] = [
        ("systemBackground", .systemBackground),
        ("systemGroupedBackground", .systemGroupedBackground),
        ("secondarySystemGroupedBackground", .secondarySystemGroupedBackground)
    ]

    @Test(arguments: [UIUserInterfaceStyle.light, .dark])
    func foregroundColorsAreReadable(style: UIUserInterfaceStyle) {
        for foreground in Self.foregrounds {
            for background in Self.backgrounds {
                let ratio = Contrast.ratio(foreground.color, background.color, style: style)
                #expect(
                    ratio >= Self.minimum,
                    "\(foreground.name) on \(background.name) (\(style == .dark ? "dark" : "light")) is \(ratio)"
                )
            }
        }
    }

    @Test(arguments: [Palette.UI.buttonTop, Palette.UI.buttonBottom])
    func whiteButtonLabelsAreReadable(fill: UIColor) {
        #expect(Contrast.ratio(.white, fill, style: .light) >= Self.minimum)
    }

    @Test func contrastMatchesKnownValues() {
        #expect(abs(Contrast.ratio(.black, .white, style: .light) - 21) < 0.01)
        #expect(abs(Contrast.ratio(.white, .white, style: .light) - 1) < 0.01)
    }
}
