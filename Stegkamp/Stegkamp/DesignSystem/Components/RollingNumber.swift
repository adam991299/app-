import SwiftUI

/// A number that rolls up from zero when it first appears and rolls to every new value.
struct RollingNumber: View {
    var value: Int
    var style: Font.TextStyle = .largeTitle
    var weight: Font.Weight = .heavy

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shownValue = 0

    var body: some View {
        Text(shownValue, format: .number)
            .numberStyle(style, weight: weight)
            .contentTransition(.numericText(value: Double(shownValue)))
            .onAppear { update(to: value) }
            .onChange(of: value) { _, newValue in update(to: newValue) }
            .accessibilityLabel(Text(value, format: .number))
    }

    private func update(to target: Int) {
        if reduceMotion {
            shownValue = target
        } else {
            withAnimation(.snappy(duration: 0.6)) {
                shownValue = target
            }
        }
    }
}

#Preview {
    @Previewable @State var steps = 6_421
    VStack(spacing: Spacing.l) {
        RollingNumber(value: steps)
        Button("Lägg till 1 234 steg") { steps += 1_234 }
            .buttonStyle(.stegSecondary)
    }
    .padding()
}
