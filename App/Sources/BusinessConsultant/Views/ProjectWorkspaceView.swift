import SwiftUI
import UniformTypeIdentifiers

struct ProjectWorkspaceView: View {
    @State var viewModel: ProjectViewModel
    @State private var isPresentingFileImporter = false
    @State private var isPresentingDeepAnalysis = false
    @State private var isPresentingDashboard = false
    @State private var isPresentingScenario = false
    @State private var isPresentingIssueTree = false

    var body: some View {
        HSplitView {
            DocumentsPanel(viewModel: viewModel, isPresentingFileImporter: $isPresentingFileImporter)
                .frame(minWidth: 220, idealWidth: 260, maxWidth: 340)

            ChatPanel(viewModel: viewModel)
                .frame(minWidth: 420)
        }
        .navigationTitle(viewModel.project.name)
        .toolbar {
            ToolbarItem {
                Button {
                    isPresentingDashboard = true
                } label: {
                    Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis")
                }
            }
            ToolbarItem {
                Button {
                    isPresentingScenario = true
                } label: {
                    Label("Scenarios", systemImage: "slider.horizontal.3")
                }
            }
            ToolbarItem {
                Button {
                    isPresentingIssueTree = true
                } label: {
                    Label("Issue Trees", systemImage: "list.bullet.indent")
                }
            }
            ToolbarItem {
                Button {
                    isPresentingDeepAnalysis = true
                } label: {
                    Label("Deep Analysis", systemImage: "chart.bar.doc.horizontal")
                }
            }
        }
        .sheet(isPresented: $isPresentingDeepAnalysis) {
            DeepAnalysisView(viewModel: viewModel)
        }
        .sheet(isPresented: $isPresentingDashboard) {
            DashboardView(viewModel: viewModel)
        }
        .sheet(isPresented: $isPresentingScenario) {
            ScenarioView(viewModel: viewModel)
        }
        .sheet(isPresented: $isPresentingIssueTree) {
            IssueTreeView(viewModel: viewModel)
        }
        .task { await viewModel.load() }
        .fileImporter(
            isPresented: $isPresentingFileImporter,
            allowedContentTypes: [.plainText, .commaSeparatedText, .pdf, .init(filenameExtension: "docx")!, .init(filenameExtension: "xlsx")!, .init(filenameExtension: "md") ?? .plainText],
            onCompletion: { result in
                if case .success(let url) = result {
                    Task { await viewModel.upload(fileURL: url) }
                }
            }
        )
        .alert(
            "Something went wrong",
            isPresented: Binding(
                get: { viewModel.errorMessage != nil },
                set: { if !$0 { viewModel.errorMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }
}

private struct DocumentsPanel: View {
    @State var viewModel: ProjectViewModel
    @Binding var isPresentingFileImporter: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Documents").font(.headline)
                Spacer()
                Button {
                    isPresentingFileImporter = true
                } label: {
                    Image(systemName: "plus")
                }
                .disabled(viewModel.isUploading)
            }
            .padding()

            if viewModel.isUploading {
                ProgressView("Parsing…").padding(.horizontal)
            }

            List(viewModel.documents) { document in
                VStack(alignment: .leading, spacing: 2) {
                    Text(document.filename).font(.body)
                    HStack(spacing: 4) {
                        StatusBadge(status: document.status)
                        if let error = document.error {
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                                .lineLimit(1)
                        }
                    }
                }
            }
            .listStyle(.sidebar)
        }
    }
}

private struct StatusBadge: View {
    let status: String

    var color: Color {
        switch status {
        case "INDEXED": return .green
        case "FAILED": return .red
        default: return .secondary
        }
    }

    var body: some View {
        Text(status.capitalized)
            .font(.caption2)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}

private struct ChatPanel: View {
    @State var viewModel: ProjectViewModel

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        if viewModel.turns.isEmpty {
                            ContentUnavailableView(
                                "Ask a question",
                                systemImage: "bubble.left.and.bubble.right",
                                description: Text("e.g. \"Why is gross margin declining?\" — grounded in the documents you've uploaded.")
                            )
                            .padding(.top, 60)
                        }

                        ForEach(viewModel.turns) { turn in
                            ChatTurnView(turn: turn).id(turn.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: viewModel.turns.count) {
                    if let last = viewModel.turns.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }

            Divider()

            HStack {
                TextField("Ask a business question…", text: $viewModel.pendingQuestion, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...4)
                    .onSubmit { Task { await viewModel.ask() } }

                if viewModel.isAsking {
                    ProgressView().controlSize(.small)
                } else {
                    Button {
                        Task { await viewModel.ask() }
                    } label: {
                        Image(systemName: "arrow.up.circle.fill")
                    }
                    .disabled(viewModel.pendingQuestion.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .padding()
        }
    }
}
