import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ notification: Notification) {
        // Deliberately synchronous, not `Task { ... }`: an unstructured Task
        // here isn't guaranteed to run before the process actually exits —
        // reproduced live, the sidecar was left running after quitting the
        // app because the Task never got scheduled in time. NSApplicationDelegate
        // callbacks run on the main thread/actor, so a direct call is safe.
        SidecarLauncher.shared.shutdown()
    }
}

@main
struct BusinessConsultantApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var appViewModel = AppViewModel()
    @State private var isSidecarReady = false

    var body: some Scene {
        WindowGroup {
            Group {
                if isSidecarReady {
                    ContentView()
                        .environment(appViewModel)
                } else {
                    SidecarLaunchView()
                }
            }
            .task {
                await SidecarLauncher.shared.ensureRunning()
                isSidecarReady = true
                await appViewModel.loadCompanies()
            }
        }
        .windowStyle(.automatic)
    }
}

/// Shown only while SidecarLauncher.ensureRunning() is checking/starting the
/// backend — usually well under a second if it's already running, up to a
/// few seconds on a cold `uv run uvicorn` start.
private struct SidecarLaunchView: View {
    @State private var launcher = SidecarLauncher.shared

    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text(launcher.statusMessage)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(40)
        .frame(minWidth: 420, minHeight: 200)
    }
}
