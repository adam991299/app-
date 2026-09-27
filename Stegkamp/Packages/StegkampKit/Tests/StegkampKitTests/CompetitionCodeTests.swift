import Testing
@testable import StegkampKit

@Suite("CompetitionCode")
struct CompetitionCodeTests {
    @Test func generatedCodesAreValid() {
        for _ in 0..<500 {
            let code = CompetitionCode.generate()
            #expect(code.count == 6)
            #expect(CompetitionCode.isValid(code))
        }
    }

    @Test func alphabetHasNoLookAlikes() {
        for character in "0O1IL" {
            #expect(!CompetitionCode.alphabet.contains(character))
        }
    }

    @Test(arguments: [
        ("k7mx2q", "K7MX2Q"),
        (" K7M-X2Q ", "K7MX2Q"),
        ("k7 mx 2q", "K7MX2Q")
    ])
    func normalizeCleansInput(input: String, expected: String) {
        #expect(CompetitionCode.normalize(input) == expected)
    }

    @Test(arguments: ["", "K7MX2", "K7MX2QQ", "K7MX0Q", "K7MXIQ", "K7MX2!"])
    func normalizeRejectsInvalidCodes(input: String) {
        #expect(CompetitionCode.normalize(input) == nil)
    }
}
