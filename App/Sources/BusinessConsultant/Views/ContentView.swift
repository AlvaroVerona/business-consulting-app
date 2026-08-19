import SwiftUI

struct ContentView: View {
    @Environment(AppViewModel.self) private var appViewModel

    var body: some View {
        @Bindable var appViewModel = appViewModel

        NavigationSplitView {
            SidebarView()
        } detail: {
            if let project = appViewModel.selectedProject {
                ProjectWorkspaceView(viewModel: ProjectViewModel(project: project))
                    .id(project.id) // fresh view model per project selection
            } else {
                ContentUnavailableView(
                    "Select a project",
                    systemImage: "briefcase",
                    description: Text("Choose a company and project from the sidebar, or create a new one.")
                )
            }
        }
        .alert(
            "Something went wrong",
            isPresented: Binding(
                get: { appViewModel.errorMessage != nil },
                set: { if !$0 { appViewModel.errorMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(appViewModel.errorMessage ?? "")
        }
    }
}
