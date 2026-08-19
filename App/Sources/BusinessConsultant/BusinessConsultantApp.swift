import SwiftUI

@main
struct BusinessConsultantApp: App {
    @State private var appViewModel = AppViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appViewModel)
                .task { await appViewModel.loadCompanies() }
        }
        .windowStyle(.automatic)
    }
}
