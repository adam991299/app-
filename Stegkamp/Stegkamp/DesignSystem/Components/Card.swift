import SwiftUI

/// The rounded surface every content block sits on.
struct Card<Content: View>: View {
    var padding: CGFloat = Spacing.m
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.surface, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
    }
}

/// A card with the brand gradient, for the one thing on a screen that should pop.
struct HeroCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(Spacing.l)
            .frame(maxWidth: .infinity, alignment: .leading)
            .foregroundStyle(.white)
            .background(Palette.buttonGradient, in: RoundedRectangle(cornerRadius: Radius.card, style: .continuous))
    }
}

#Preview {
    ScrollView {
        VStack(spacing: Spacing.m) {
            Card {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Veckokampen").font(.cardTitle)
                    Text("412 steg efter Anna").foregroundStyle(.secondary)
                }
            }
            HeroCard {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    Text("Du leder!").font(.cardTitle)
                    Text("1 204 steg före tvåan")
                }
            }
        }
        .padding()
    }
    .background(Palette.background)
}
