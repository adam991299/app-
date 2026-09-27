import SwiftUI

@main
struct StegkampApp: App {
    @State private var environment: AppEnvironment

    init() {
        FirebaseBootstrap.configureIfAvailable()
        _environment = State(initialValue: AppEnvironment.makeForLaunch())
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(environment)
        }
    }
}
