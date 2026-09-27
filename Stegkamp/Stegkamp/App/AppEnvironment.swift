import Observation

/// The app's dependency container, injected into the SwiftUI environment.
///
/// Every service the app talks to is reached through here, so previews and UI tests can swap in
/// mocks without touching the views.
@Observable
@MainActor
final class AppEnvironment {
    enum Backend: Equatable {
        /// Firebase is configured with `GoogleService-Info.plist`.
        case firebase
        /// No Firebase configuration: the app runs on local sample data.
        case demo
    }

    let backend: Backend

    init(backend: Backend) {
        self.backend = backend
    }

    static func makeForLaunch() -> AppEnvironment {
        AppEnvironment(backend: FirebaseBootstrap.isConfigured ? .firebase : .demo)
    }

    static let preview = AppEnvironment(backend: .demo)
}
