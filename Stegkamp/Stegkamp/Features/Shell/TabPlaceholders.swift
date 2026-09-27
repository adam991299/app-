import SwiftUI

// The three tabs show designed empty states until their features land (Idag in phase 1,
// Tävlingar in phase 3, Profil in phase 2).

struct TodayPlaceholderView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: Spacing.l) {
                    StepRing(progress: 0)
                        .frame(maxWidth: 240)
                        .overlay {
                            VStack(spacing: Spacing.xxs) {
                                RollingNumber(value: 0)
                                Text("steg idag")
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.top, Spacing.l)

                    EmptyStateView(
                        symbol: "heart.text.square.fill",
                        title: "Snart ser du dina steg här",
                        message: "När Stegkamp får läsa från Hälsa fylls ringen i takt med att du går."
                    )
                }
                .padding(.horizontal, Spacing.m)
            }
            .background(Palette.background)
            .navigationTitle("Idag")
        }
    }
}

struct CompetitionsPlaceholderView: View {
    var body: some View {
        NavigationStack {
            EmptyStateView(
                symbol: "trophy.fill",
                title: "Inga tävlingar än",
                message: "Snart kan du utmana vännerna och se vem som går mest."
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Palette.background)
            .navigationTitle("Tävlingar")
        }
    }
}

struct ProfilePlaceholderView: View {
    @Environment(AppEnvironment.self) private var environment

    var body: some View {
        NavigationStack {
            List {
                Section {
                    LabeledContent("Backend") {
                        switch environment.backend {
                        case .firebase: Text(verbatim: "Firebase")
                        case .demo: Text("Demoläge")
                        }
                    }
                } footer: {
                    if environment.backend == .demo {
                        Text("Lägg till GoogleService-Info.plist för att ansluta till Firebase.")
                    }
                }

                #if DEBUG
                Section("Utvecklare") {
                    NavigationLink("Designsystem") {
                        DesignSystemGallery()
                    }
                }
                #endif
            }
            .navigationTitle("Profil")
        }
    }
}

#Preview("Idag") {
    TodayPlaceholderView()
}

#Preview("Tävlingar") {
    CompetitionsPlaceholderView()
}

#Preview("Profil") {
    ProfilePlaceholderView()
        .environment(AppEnvironment.preview)
}
