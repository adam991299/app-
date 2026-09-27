import Foundation

/// An amount of Swedish kronor stored as whole öre, so pot math never touches floating point.
public struct Money: Hashable, Comparable, Codable, Sendable {
    public var ore: Int

    public init(ore: Int) {
        self.ore = ore
    }

    public init(kronor: Int) {
        self.ore = kronor * 100
    }

    public static let zero = Money(ore: 0)

    public var isWholeKronor: Bool { ore % 100 == 0 }

    public static func < (lhs: Money, rhs: Money) -> Bool { lhs.ore < rhs.ore }
    public static func + (lhs: Money, rhs: Money) -> Money { Money(ore: lhs.ore + rhs.ore) }
    public static func - (lhs: Money, rhs: Money) -> Money { Money(ore: lhs.ore - rhs.ore) }
    public static func * (lhs: Money, rhs: Int) -> Money { Money(ore: lhs.ore * rhs) }
    public static prefix func - (value: Money) -> Money { Money(ore: -value.ore) }

    /// "50 kr" for whole kronor, "12,50 kr" otherwise (Swedish formatting by default).
    public func formatted(locale: Locale = Locale(identifier: "sv_SE")) -> String {
        let amount = Decimal(ore) / 100
        return amount.formatted(
            .currency(code: "SEK")
                .locale(locale)
                .precision(.fractionLength(isWholeKronor ? 0 : 2))
        )
    }

    /// Decimal string for payment links, e.g. "50" or "12.50". Always uses a dot.
    public var paymentAmountString: String {
        let kronor = ore / 100
        let rest = abs(ore % 100)
        return rest == 0 ? "\(kronor)" : "\(kronor).\(rest < 10 ? "0" : "")\(rest)"
    }
}
