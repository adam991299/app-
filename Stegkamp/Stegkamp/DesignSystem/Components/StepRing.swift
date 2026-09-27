import SwiftUI

/// The daily goal ring. Fills clockwise from the top; past 100 % a second, glowing lap starts.
struct StepRing: View {
    /// Fraction of the goal reached. Values above 1 draw the overflow lap (capped at 2).
    var progress: Double
    var lineWidth: CGFloat = 24

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shownProgress: Double = 0

    var body: some View {
        GeometryReader { proxy in
            let diameter = min(proxy.size.width, proxy.size.height)
            ZStack {
                Circle()
                    .stroke(Palette.ringTrack, lineWidth: lineWidth)

                arc(to: min(shownProgress, 1))

                // Round start cap in the start color, so the gradient seam at 12 o'clock never shows.
                Circle()
                    .fill(Palette.glowStart)
                    .frame(width: lineWidth, height: lineWidth)
                    .offset(y: -diameter / 2)
                    .opacity(shownProgress > 0 ? 1 : 0)

                if shownProgress > 1 {
                    arc(to: min(shownProgress - 1, 1))
                        .shadow(color: .black.opacity(0.25), radius: lineWidth / 4)
                }
            }
            .frame(width: diameter, height: diameter)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .padding(lineWidth / 2)
        .aspectRatio(1, contentMode: .fit)
        .onAppear { animate(to: progress) }
        .onChange(of: progress) { _, newValue in animate(to: newValue) }
        .accessibilityElement()
        .accessibilityLabel(Text("Dagens mål"))
        .accessibilityValue(Text(progress.clamped(to: 0...2), format: .percent.precision(.fractionLength(0))))
    }

    private func arc(to end: Double) -> some View {
        Circle()
            .trim(from: 0, to: end)
            .stroke(
                AngularGradient(
                    colors: [Palette.glowStart, Palette.glowEnd],
                    center: .center,
                    startAngle: .degrees(0),
                    endAngle: .degrees(360)
                ),
                style: StrokeStyle(lineWidth: lineWidth, lineCap: .round)
            )
            .rotationEffect(.degrees(-90))
    }

    private func animate(to target: Double) {
        let clamped = target.clamped(to: 0...2)
        if reduceMotion {
            shownProgress = clamped
        } else {
            withAnimation(.spring(duration: 1.1, bounce: 0.18)) {
                shownProgress = clamped
            }
        }
    }
}

#Preview("Ring") {
    VStack(spacing: Spacing.xl) {
        StepRing(progress: 0.64)
            .frame(width: 220)
        HStack(spacing: Spacing.l) {
            StepRing(progress: 0, lineWidth: 12).frame(width: 80)
            StepRing(progress: 1, lineWidth: 12).frame(width: 80)
            StepRing(progress: 1.35, lineWidth: 12).frame(width: 80)
        }
    }
    .padding()
}
