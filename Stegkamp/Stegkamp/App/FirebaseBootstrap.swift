import FirebaseCore
import Foundation
import OSLog

/// Configures Firebase when `GoogleService-Info.plist` is bundled.
///
/// Without it (before the Firebase project exists, in previews and in UI tests) the app still
/// launches and runs in demo mode.
@MainActor
enum FirebaseBootstrap {
    private(set) static var isConfigured = false

    static func configureIfAvailable() {
        guard !isConfigured else { return }
        guard !LaunchArguments.isUITesting, !isRunningInPreview else { return }
        guard Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist") != nil else {
            Logger.app.notice("GoogleService-Info.plist saknas – appen körs i demoläge.")
            return
        }
        FirebaseApp.configure()
        isConfigured = true
    }

    private static var isRunningInPreview: Bool {
        ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1"
    }
}

extension Logger {
    static let app = Logger(subsystem: Bundle.main.bundleIdentifier ?? "Stegkamp", category: "app")
}
