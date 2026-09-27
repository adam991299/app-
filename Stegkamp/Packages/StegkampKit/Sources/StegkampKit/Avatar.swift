import Foundation

/// A participant's avatar: an emoji on a tinted circle, or an uploaded photo.
public enum Avatar: Hashable, Codable, Sendable {
    case emoji(String)
    case photo(URL)

    public static let `default` = Avatar.emoji("🏃")

    /// Emojis offered in onboarding and the profile editor.
    public static let suggestedEmojis = [
        "🏃", "🚶", "🦊", "🐻", "🐯", "🦄", "🐙", "🐸",
        "🦁", "🐼", "🐧", "🦉", "🌟", "🔥", "⚡️", "🌈",
        "🍀", "🍉", "🚀", "👟", "🏔️", "🌊", "🎧", "😎"
    ]
}
