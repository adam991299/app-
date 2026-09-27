import SwiftUI

extension View {
    /// Placeholder look while data loads: redacted content with a soft shimmer.
    /// The shimmer is skipped with Reduce Motion.
    func skeleton(_ isActive: Bool) -> some View {
        modifier(SkeletonModifier(isActive: isActive))
    }
}

private struct SkeletonModifier: ViewModifier {
    var isActive: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        if isActive {
            content
                .redacted(reason: .placeholder)
                .allowsHitTesting(false)
                .overlay {
                    if !reduceMotion {
                        shimmer.mask(content.redacted(reason: .placeholder))
                    }
                }
                .accessibilityLabel(Text("Laddar"))
                .onAppear {
                    guard !reduceMotion else { return }
                    withAnimation(.linear(duration: 1.3).repeatForever(autoreverses: false)) {
                        phase = 1
                    }
                }
        } else {
            content
        }
    }

    private var shimmer: some View {
        GeometryReader { proxy in
            LinearGradient(
                colors: [.clear, .white.opacity(0.45), .clear],
                startPoint: .leading,
                endPoint: .trailing
            )
            .frame(width: proxy.size.width * 0.6)
            .offset(x: phase * proxy.size.width * 1.2)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .blendMode(.plusLighter)
    }
}

#Preview {
    @Previewable @State var isLoading = true
    VStack(spacing: Spacing.m) {
        Card {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Veckokampen").font(.cardTitle)
                Text("Du ligger 2:a av 6").foregroundStyle(.secondary)
            }
        }
        .skeleton(isLoading)
        Toggle("Laddar", isOn: $isLoading)
    }
    .padding()
    .background(Palette.background)
}
