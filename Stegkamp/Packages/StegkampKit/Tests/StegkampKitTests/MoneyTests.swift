import Foundation
import Testing
@testable import StegkampKit

@Suite("Money")
struct MoneyTests {
    private func normalizedSpaces(_ string: String) -> String {
        string.replacingOccurrences(of: "\u{00A0}", with: " ")
            .replacingOccurrences(of: "\u{202F}", with: " ")
    }

    @Test func wholeKronorHaveNoDecimals() {
        #expect(normalizedSpaces(Money(kronor: 50).formatted()) == "50 kr")
        #expect(normalizedSpaces(Money(kronor: 1250).formatted()) == "1 250 kr")
    }

    @Test func oreAreShownWithTwoDecimals() {
        #expect(normalizedSpaces(Money(ore: 1250).formatted()) == "12,50 kr")
        #expect(normalizedSpaces(Money(ore: 3334).formatted()) == "33,34 kr")
    }

    @Test func paymentAmountUsesDotAndTwoDecimals() {
        #expect(Money(kronor: 50).paymentAmountString == "50")
        #expect(Money(ore: 1250).paymentAmountString == "12.50")
        #expect(Money(ore: 3305).paymentAmountString == "33.05")
    }

    @Test func arithmetic() {
        #expect(Money(kronor: 50) * 5 == Money(kronor: 250))
        #expect(Money(kronor: 100) - Money(ore: 3334) == Money(ore: 6666))
        #expect(-Money(ore: 5) + Money(ore: 5) == .zero)
    }
}
