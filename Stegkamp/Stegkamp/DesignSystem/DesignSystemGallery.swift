import StegkampKit
import SwiftUI

/// Every design-system component on one screen, for checking light/dark mode, Dynamic Type and
/// Reduce Motion on a real device. Reachable from Profil → Utvecklare in debug builds.
struct DesignSystemGallery: View {
    @State private var progress = 0.64
    @State private var steps = 6_421
    @State private var isLoading = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Spacing.l) {
                section("Stegring") {
                    StepRing(progress: progress)
                        .frame(maxWidth: 220)
                        .frame(maxWidth: .infinity)
                    Slider(value: $progress, in: 0...1.6)
                        .tint(Palette.accent)
                }

                section("Siffror") {
                    RollingNumber(value: steps)
                    Button("Gå 1 234 steg") {
                        steps += 1_234
                        Haptics.tap()
                    }
                    .buttonStyle(.stegSecondary)
                }

                section("Färger") {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 64))], spacing: Spacing.s) {
                        swatch(Palette.accent, "Glöd")
                        swatch(Palette.success, "Mynta")
                        swatch(Palette.gold, "Guld")
                        swatch(Palette.silver, "Silver")
                        swatch(Palette.bronze, "Brons")
                        swatch(Palette.midnight, "Midnatt")
                    }
                    RoundedRectangle(cornerRadius: Radius.tile, style: .continuous)
                        .fill(Palette.glowGradient)
                        .frame(height: 56)
                }

                section("Kort") {
                    Card {
                        HStack(spacing: Spacing.s) {
                            AvatarView(avatar: .emoji("🦊"), isHighlighted: true)
                            VStack(alignment: .leading) {
                                Text("Veckokampen").font(.headline)
                                Text("412 steg efter Anna").foregroundStyle(.secondary)
                            }
                            Spacer()
                            Pill(text: "2:a")
                        }
                    }
                    .skeleton(isLoading)
                    Toggle("Visa laddning", isOn: $isLoading)
                    HeroCard {
                        Text("Du vann Veckokampen! 🏆").font(.cardTitle)
                    }
                    HStack(spacing: Spacing.s) {
                        StatTile(symbol: "flame.fill", value: "12", caption: "dagar i rad")
                        StatTile(symbol: "map.fill", value: "5,4 km", caption: "distans", tint: Palette.success)
                    }
                }

                section("Knappar") {
                    Button("Skapa tävling") { Haptics.success() }
                        .buttonStyle(.stegPrimary)
                    Button("Gå med med kod") { Haptics.tap() }
                        .buttonStyle(.stegSecondary)
                }

                section("Tomt läge") {
                    EmptyStateView(
                        symbol: "figure.walk.motion",
                        title: "Inga steg än idag",
                        message: "Ta en promenad så fylls ringen."
                    )
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(Spacing.m)
        }
        .background(Palette.background)
        .navigationTitle("Designsystem")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func section(_ title: LocalizedStringKey, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: Spacing.s) {
            Text(title)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            content()
        }
    }

    private func swatch(_ color: Color, _ name: LocalizedStringKey) -> some View {
        VStack(spacing: Spacing.xxs) {
            RoundedRectangle(cornerRadius: Radius.tile, style: .continuous)
                .fill(color)
                .frame(height: 48)
            Text(name).font(.caption)
        }
    }
}

#Preview {
    NavigationStack {
        DesignSystemGallery()
    }
}
