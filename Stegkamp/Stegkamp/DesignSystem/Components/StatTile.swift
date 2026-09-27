import SwiftUI

/// A compact statistic: symbol, big rounded number and a caption.
struct StatTile: View {
    var symbol: String
    var value: String
    var caption: LocalizedStringKey
    var tint: Color = Palette.accent

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xxs) {
            Image(systemName: symbol)
                .font(.headline)
                .foregroundStyle(tint)
                .accessibilityHidden(true)
            Text(value)
                .numberStyle(.title2)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(caption)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(Spacing.s)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.surface, in: RoundedRectangle(cornerRadius: Radius.tile, style: .continuous))
        .accessibilityElement(children: .combine)
    }
}

/// A small capsule label, e.g. "Du" or "Under granskning".
struct Pill: View {
    var text: LocalizedStringKey
    var tint: Color = Palette.accent

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(tint)
            .padding(.horizontal, Spacing.xs)
            .padding(.vertical, Spacing.xxs / 2)
            .background(tint.opacity(0.14), in: Capsule())
    }
}

#Preview {
    VStack(spacing: Spacing.m) {
        HStack(spacing: Spacing.s) {
            StatTile(symbol: "flame.fill", value: "12", caption: "dagar i rad")
            StatTile(symbol: "map.fill", value: "5,4 km", caption: "distans", tint: Palette.success)
        }
        HStack {
            Pill(text: "Du")
            Pill(text: "Under granskning", tint: .secondary)
        }
    }
    .padding()
    .background(Palette.background)
}
