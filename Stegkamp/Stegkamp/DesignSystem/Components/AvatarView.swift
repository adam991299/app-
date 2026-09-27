import StegkampKit
import SwiftUI

/// A participant's avatar. `isHighlighted` draws the accent ring used to mark "you".
struct AvatarView: View {
    var avatar: Avatar
    var size: CGFloat = 44
    var isHighlighted = false

    var body: some View {
        content
            .frame(width: size, height: size)
            .clipShape(Circle())
            .overlay {
                if isHighlighted {
                    Circle().strokeBorder(Palette.accent, lineWidth: max(2, size / 18))
                }
            }
            .accessibilityHidden(true)
    }

    @ViewBuilder
    private var content: some View {
        switch avatar {
        case .emoji(let emoji):
            ZStack {
                Circle().fill(Palette.accent.opacity(0.14))
                Text(emoji)
                    .font(.system(size: size * 0.55))
                    .minimumScaleFactor(0.5)
            }
        case .photo(let url):
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    image.resizable().scaledToFill()
                default:
                    Circle().fill(Color(uiColor: .tertiarySystemFill))
                }
            }
        }
    }
}

#Preview {
    HStack(spacing: Spacing.m) {
        AvatarView(avatar: .emoji("🦊"))
        AvatarView(avatar: .emoji("🚀"), size: 64, isHighlighted: true)
        AvatarView(avatar: .default, size: 32)
    }
    .padding()
}
