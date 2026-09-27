import SwiftUI

/// Friendly empty and error states: a gradient symbol, a short headline and one optional action.
struct EmptyStateView: View {
    var symbol: String
    var title: LocalizedStringKey
    var message: LocalizedStringKey
    var actionTitle: LocalizedStringKey?
    var action: (() -> Void)?

    @ScaledMetric(relativeTo: .largeTitle) private var symbolSize: CGFloat = 56

    var body: some View {
        VStack(spacing: Spacing.m) {
            Image(systemName: symbol)
                .font(.system(size: symbolSize, weight: .semibold))
                .foregroundStyle(Palette.glowGradient)
                .symbolRenderingMode(.hierarchical)
                .accessibilityHidden(true)

            VStack(spacing: Spacing.xs) {
                Text(title)
                    .font(.cardTitle)
                    .multilineTextAlignment(.center)
                Text(message)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            if let actionTitle, let action {
                Button(actionTitle, action: action)
                    .buttonStyle(.stegPrimary)
                    .padding(.top, Spacing.xs)
            }
        }
        .padding(Spacing.xl)
        .frame(maxWidth: 420)
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    EmptyStateView(
        symbol: "trophy.fill",
        title: "Inga tävlingar än",
        message: "Starta en tävling och bjud in vännerna – det tar tio sekunder.",
        actionTitle: "Skapa tävling",
        action: {}
    )
}
