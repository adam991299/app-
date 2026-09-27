import SwiftUI

/// Full-width, gradient-filled call to action. One per screen.
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(isEnabled ? Color.white : Color.secondary)
            .frame(maxWidth: .infinity, minHeight: 54)
            .padding(.horizontal, Spacing.m)
            .background {
                RoundedRectangle(cornerRadius: Radius.button, style: .continuous)
                    .fill(isEnabled ? AnyShapeStyle(Palette.buttonGradient) : AnyShapeStyle(Color(uiColor: .tertiarySystemFill)))
            }
            .contentShape(RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
            .pressEffect(isPressed: configuration.isPressed)
    }
}

/// Tinted secondary action.
struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(Palette.accent)
            .frame(maxWidth: .infinity, minHeight: 50)
            .padding(.horizontal, Spacing.m)
            .background(
                Palette.accent.opacity(0.12),
                in: RoundedRectangle(cornerRadius: Radius.button, style: .continuous)
            )
            .contentShape(RoundedRectangle(cornerRadius: Radius.button, style: .continuous))
            .pressEffect(isPressed: configuration.isPressed)
    }
}

private struct PressEffect: ViewModifier {
    var isPressed: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .scaleEffect(isPressed && !reduceMotion ? 0.97 : 1)
            .opacity(isPressed ? 0.85 : 1)
            .animation(.spring(duration: 0.25, bounce: 0.3), value: isPressed)
    }
}

private extension View {
    func pressEffect(isPressed: Bool) -> some View {
        modifier(PressEffect(isPressed: isPressed))
    }
}

extension ButtonStyle where Self == PrimaryButtonStyle {
    static var stegPrimary: PrimaryButtonStyle { PrimaryButtonStyle() }
}

extension ButtonStyle where Self == SecondaryButtonStyle {
    static var stegSecondary: SecondaryButtonStyle { SecondaryButtonStyle() }
}

#Preview {
    VStack(spacing: Spacing.s) {
        Button("Skapa tävling") {}
            .buttonStyle(.stegPrimary)
        Button("Gå med med kod") {}
            .buttonStyle(.stegSecondary)
        Button("Inaktiv") {}
            .buttonStyle(.stegPrimary)
            .disabled(true)
    }
    .padding()
}
