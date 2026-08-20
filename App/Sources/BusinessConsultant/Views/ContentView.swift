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
        .copyableErrorSheet(message: $appViewModel.errorMessage)
    }
}
