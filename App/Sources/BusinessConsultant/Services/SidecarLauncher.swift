import Foundation
#if canImport(Darwin)
import Darwin
#endif

/// Auto-starts the Python sidecar (`uv run uvicorn src.main:app --port 8765`)
/// so the app is launchable from Finder/Spotlight without a separate
/// Terminal step, and stops the process it started when the app quits.
///
/// This is a personal, single-machine dev tool (see ../../../README.md — the
/// packaged .app is ad-hoc signed for local use, not notarized for
/// distribution), so a fixed, known sidecar source location is an acceptable
/// trade-off rather than solving for "this app on someone else's machine."
/// Override with the BUSINESS_CONSULTANT_SIDECAR_PATH environment variable
/// if the repo ever lives somewhere else.
@MainActor
@Observable
final class SidecarLauncher {
    static let shared = SidecarLauncher()

    private var process: Process?
    private(set) var didLaunchSidecar = false
    private(set) var statusMessage = "Starting local backend..."

    private init() {}

    private var sidecarDirectory: URL {
        if let override = ProcessInfo.processInfo.environment["BUSINESS_CONSULTANT_SIDECAR_PATH"] {
            return URL(fileURLWithPath: override)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Documents/ai_for_business/business-consulting-app/sidecar")
    }

    /// Waits (briefly) for the sidecar to be reachable, launching it first if
    /// nothing answered on the first check. Always returns — a failure to
    /// launch or a slow startup surfaces later as ordinary per-request
    /// errors (SidecarClient already has error handling for that), not as a
    /// blocking failure of app launch itself.
    func ensureRunning() async {
        if await SidecarClient.shared.isHealthy() {
            statusMessage = "Connected."
            return
        }

        guard FileManager.default.fileExists(atPath: sidecarDirectory.path) else {
            statusMessage = "Sidecar not found at \(sidecarDirectory.path) — start it manually (see README)."
            return
        }

        // Two near-simultaneous launches (Dock + Spotlight, or a quick
        // relaunch) can both observe "not healthy yet" and both try to spawn
        // a sidecar, racing for port 8765 — the loser crashes on bind and
        // its instance shows a misleading "taking longer than expected"
        // instead of just waiting for the winner. The lock makes only one
        // instance actually attempt the spawn; the rest wait and poll.
        guard acquireLaunchLock() else {
            statusMessage = "Waiting for another launch of this app to start the backend..."
            await waitUntilHealthyOrTimeout(seconds: 20)
            return
        }
        defer { releaseLaunchLock() }

        guard let uvPath = Self.resolveUvExecutable() else {
            statusMessage = "`uv` not found — start the sidecar manually (see README)."
            return
        }

        launch(uvPath: uvPath)
        await waitUntilHealthyOrTimeout(seconds: 15)
    }

    /// Only terminates a process this instance actually spawned — a sidecar
    /// that was already running before this app launched (started manually,
    /// or by another instance) is left alone.
    ///
    /// Signals the whole process GROUP, not just the direct child: `uv run`
    /// spawns uvicorn as its own child process in the same group, and `uv`
    /// does not reliably forward SIGTERM to it — reproduced live: quitting
    /// the app terminated `uv`'s direct PID but left the actual uvicorn
    /// process running and still serving requests. `process.terminate()`
    /// alone only signals the single PID Foundation launched.
    func shutdown() {
        guard didLaunchSidecar, let process, process.isRunning else { return }

        let pid = process.processIdentifier
        let pgid = getpgid(pid)
        let target = pgid > 0 ? -pgid : pid

        kill(target, SIGTERM)

        // Brief synchronous wait before escalating — acceptable here since
        // this only runs once, during app quit, and needs to complete
        // before applicationWillTerminate returns (see AppDelegate).
        usleep(300_000)
        if process.isRunning {
            kill(target, SIGKILL)
        }
    }

    private var lockFileURL: URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("business-consultant-sidecar.lock")
    }

    /// Atomic exclusive-create lock (`O_CREAT|O_EXCL`, not check-then-create,
    /// which would have the same race this exists to close) so only one
    /// concurrently-launching app instance spawns the sidecar. Stores the
    /// owning process's pid in the file and treats the lock as stale (and
    /// reclaims it) if that process is no longer alive — otherwise a crash
    /// between acquiring the lock and releasing it would wedge every future
    /// launch.
    private func acquireLaunchLock() -> Bool {
        if tryCreateLockFile() { return true }

        if let contents = try? String(contentsOf: lockFileURL, encoding: .utf8),
           let ownerPid = pid_t(contents.trimmingCharacters(in: .whitespacesAndNewlines)),
           kill(ownerPid, 0) == 0 {
            return false  // a live process holds the lock
        }

        // Stale lock — the owner crashed or exited without releasing it.
        // Reclaiming can itself lose a race to another instance doing the
        // same thing, which tryCreateLockFile's O_EXCL correctly rejects.
        try? FileManager.default.removeItem(at: lockFileURL)
        return tryCreateLockFile()
    }

    private func tryCreateLockFile() -> Bool {
        let fd = open(lockFileURL.path, O_CREAT | O_EXCL | O_WRONLY, 0o644)
        guard fd >= 0 else { return false }

        let pidString = "\(ProcessInfo.processInfo.processIdentifier)"
        _ = pidString.withCString { write(fd, $0, strlen($0)) }
        close(fd)
        return true
    }

    private func releaseLaunchLock() {
        try? FileManager.default.removeItem(at: lockFileURL)
    }

    private func launch(uvPath: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: uvPath)
        process.arguments = ["run", "uvicorn", "src.main:app", "--port", "8765"]
        process.currentDirectoryURL = sidecarDirectory

        let logURL = FileManager.default.temporaryDirectory.appendingPathComponent("business-consultant-sidecar.log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        if let handle = try? FileHandle(forWritingTo: logURL) {
            process.standardOutput = handle
            process.standardError = handle
        }

        do {
            try process.run()
            self.process = process
            self.didLaunchSidecar = true
            statusMessage = "Starting local backend (log: \(logURL.path))..."
        } catch {
            statusMessage = "Failed to launch the sidecar: \(error.localizedDescription)"
        }
    }

    private func waitUntilHealthyOrTimeout(seconds: TimeInterval) async {
        let deadline = Date().addingTimeInterval(seconds)

        while Date() < deadline {
            if await SidecarClient.shared.isHealthy() {
                statusMessage = "Connected."
                return
            }
            try? await Task.sleep(nanoseconds: 300_000_000)
        }

        statusMessage = "The sidecar is taking longer than expected to start — continuing anyway."
    }

    /// A GUI app launched via Finder/`open` doesn't inherit the login
    /// shell's PATH (no .zshrc/.bash_profile sourcing), so `uv` frequently
    /// isn't resolvable the way it is from Terminal — check the common
    /// install locations directly instead of relying on PATH lookup.
    private static func resolveUvExecutable() -> String? {
        let candidates = [
            "\(NSHomeDirectory())/.local/bin/uv",
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
        ]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }
}
