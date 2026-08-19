import SwiftUI

/// Spec section 4 (Issue Trees) / section 2 Deep Analysis mode step 4 / MVP
/// DoD #6. The user defines the question (step 3 of that same workflow is
/// "define the key question" as its own deliberate step) — this is never
/// auto-triggered from a Concern's title, since a guessed question would
/// produce a weaker tree than one the user actually means to investigate.
struct IssueTreeView: View {
    @State var viewModel: ProjectViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                questionBar

                if viewModel.issueTrees.isEmpty {
                    ContentUnavailableView(
                        "No issue trees yet",
                        systemImage: "chart.bar.doc.horizontal",
                        description: Text("Ask a diagnostic question (e.g. \"Why did EBITDA decline?\") to get a MECE-where-possible breakdown to investigate.")
                    )
                    .frame(maxHeight: .infinity)
                } else {
                    List {
                        ForEach(viewModel.issueTrees) { tree in
                            Section {
                                if let overallNote = tree.overallNote {
                                    Label(overallNote, systemImage: "exclamationmark.triangle")
                                        .font(.caption)
                                        .foregroundStyle(.orange)
                                }
                                OutlineGroup(tree.rootChildren, children: \.nonEmptyChildren) { node in
                                    IssueNodeLabel(node: node)
                                }
                            } header: {
                                Text(tree.question).font(.headline)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Issue Trees")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
        .frame(minWidth: 560, minHeight: 520)
    }

    private var questionBar: some View {
        HStack {
            TextField("e.g. Why did EBITDA decline?", text: $viewModel.pendingIssueTreeQuestion, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...3)
                .onSubmit { Task { await viewModel.buildIssueTree() } }

            if viewModel.isBuildingIssueTree {
                ProgressView().controlSize(.small)
            } else {
                Button("Build") {
                    Task { await viewModel.buildIssueTree() }
                }
                .disabled(viewModel.pendingIssueTreeQuestion.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding()
    }
}

private struct IssueNodeLabel: View {
    let node: IssueNode

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(alignment: .top, spacing: 6) {
                Text(node.label).font(.callout)
                if node.isForcedMece {
                    Label("Overlap", systemImage: "arrow.triangle.branch")
                        .font(.caption2.weight(.semibold))
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Color.orange.opacity(0.15))
                        .foregroundStyle(.orange)
                        .clipShape(Capsule())
                }
            }
            if node.isForcedMece, let note = node.overlapNote {
                Text(note).font(.caption2).foregroundStyle(.secondary)
            }
        }
    }
}
