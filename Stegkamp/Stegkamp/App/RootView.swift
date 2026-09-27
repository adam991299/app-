import SwiftUI

struct RootView: View {
    enum Tab: Hashable {
        case today, competitions, profile
    }

    @State private var selection: Tab = .today

    var body: some View {
        TabView(selection: $selection) {
            TodayPlaceholderView()
                .tabItem { Label("Idag", systemImage: "figure.walk") }
                .tag(Tab.today)

            CompetitionsPlaceholderView()
                .tabItem { Label("Tävlingar", systemImage: "trophy") }
                .tag(Tab.competitions)

            ProfilePlaceholderView()
                .tabItem { Label("Profil", systemImage: "person.crop.circle") }
                .tag(Tab.profile)
        }
    }
}

#Preview {
    RootView()
        .environment(AppEnvironment.preview)
}
