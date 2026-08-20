import Quartz
import SwiftUI

/// Downloads a document's original bytes (not the parsed/chunked text) and
/// renders them with macOS Quick Look — PDF/CSV/DOCX/MD/XLSX all get a
/// reasonable native preview for free this way, without this app writing
/// its own per-file-type renderer.
struct DocumentPreviewSheet: View {
    let document: BusinessDocument
    let viewModel: ProjectViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var localFileURL: URL?
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(document.filename).font(.headline)
                Spacer()
                Button("Close") { dismiss() }
            }
            .padding()

            Divider()

            Group {
                if let localFileURL {
                    QuickLookView(url: localFileURL)
                } else if let errorMessage {
                    ContentUnavailableView(
                        "Couldn't load preview",
                        systemImage: "doc.questionmark",
                        description: Text(errorMessage)
                    )
                } else {
                    ProgressView("Loading preview…")
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(minWidth: 560, minHeight: 480)
        .task { await load() }
        .onDisappear {
            if let localFileURL { try? FileManager.default.removeItem(at: localFileURL) }
        }
    }

    private func load() async {
        do {
            let data = try await viewModel.downloadDocumentContent(documentId: document.id)

            // `.task` cancels cooperatively when the sheet is dismissed, but
            // that isn't checked automatically after an `await` returns —
            // without this, a download that completes just after dismissal
            // would still write a temp file and set localFileURL *after*
            // onDisappear's cleanup already ran (and saw localFileURL == nil,
            // nothing to remove), leaking the file. Bail out before writing
            // anything if that happened.
            guard !Task.isCancelled else { return }

            // Quick Look renders based on the file extension, so the temp
            // file needs the original document's extension, not a bare UUID.
            let pathExtension = URL(fileURLWithPath: document.filename).pathExtension
            let tempURL = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension(pathExtension)
            try data.write(to: tempURL)

            guard !Task.isCancelled else {
                try? FileManager.default.removeItem(at: tempURL)
                return
            }
            localFileURL = tempURL
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct QuickLookView: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> QLPreviewView {
        let view = QLPreviewView(frame: .zero, style: .normal) ?? QLPreviewView()
        view.previewItem = url as QLPreviewItem
        return view
    }

    func updateNSView(_ nsView: QLPreviewView, context: Context) {
        nsView.previewItem = url as QLPreviewItem
    }
}
