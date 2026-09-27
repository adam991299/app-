import Foundation

/// Flags passed by UI tests and screenshot automation.
enum LaunchArguments {
    /// Run against in-memory mock services: no network, no HealthKit, deterministic data.
    static let uiTesting = "-ui-testing"

    static var isUITesting: Bool {
        ProcessInfo.processInfo.arguments.contains(uiTesting)
    }
}
