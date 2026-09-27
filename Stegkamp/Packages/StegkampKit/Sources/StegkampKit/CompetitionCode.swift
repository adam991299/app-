/// Six-character join codes such as "K7MX2Q".
///
/// The alphabet leaves out look-alike characters (0/O, 1/I/L) so codes survive being read aloud or
/// typed from a screenshot. The server generates codes with the same alphabet
/// (`firebase/functions/src/lib/inviteCode.ts`).
public enum CompetitionCode {
    public static let alphabet: [Character] = Array("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
    public static let length = 6

    public static func generate<G: RandomNumberGenerator>(using generator: inout G) -> String {
        String((0..<length).map { _ in alphabet.randomElement(using: &generator)! })
    }

    public static func generate() -> String {
        var generator = SystemRandomNumberGenerator()
        return generate(using: &generator)
    }

    /// Uppercases the input and strips spaces and dashes.
    /// Returns `nil` when the result is not a valid code.
    public static func normalize(_ input: String) -> String? {
        let cleaned = input
            .uppercased()
            .filter { !$0.isWhitespace && $0 != "-" }
        return isValid(cleaned) ? cleaned : nil
    }

    public static func isValid(_ code: String) -> Bool {
        code.count == length && code.allSatisfy(alphabet.contains)
    }
}
