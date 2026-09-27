import SwiftUI

extension Font {
    /// SF Pro Rounded at a Dynamic Type style. Used for every number in the app.
    static func rounded(_ style: Font.TextStyle, weight: Font.Weight = .bold) -> Font {
        .system(style, design: .rounded, weight: weight)
    }

    /// Screen titles inside cards and sheets.
    static let cardTitle = Font.system(.title3, design: .rounded, weight: .bold)
}

extension View {
    /// Rounded, tabular digits so numbers do not wobble while they roll.
    func numberStyle(_ style: Font.TextStyle, weight: Font.Weight = .bold) -> some View {
        font(.rounded(style, weight: weight)).monospacedDigit()
    }
}
