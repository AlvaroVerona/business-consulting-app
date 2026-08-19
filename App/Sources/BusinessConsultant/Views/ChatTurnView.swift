import SwiftUI

/// Renders one Quick Answer turn in the spec's fixed shape (section 2):
/// Answer, Evidence, Reasoning, Confidence, Missing information, Recommended
/// next question. Nothing here is prose the LLM was free to structure itself.
struct ChatTurnView: View {
    let turn: ChatTurn

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "person.circle.fill").foregroundStyle(.secondary)
                Text(turn.question).font(.body.weight(.medium))
            }

            if let answer = turn.answer {
                QuickAnswerCard(answer: answer)
            } else if let error = turn.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
                    .font(.callout)
            } else {
                ProgressView("Analyzing…").padding(.leading, 28)
            }
        }
        .padding()
        .background(.quaternary.opacity(0.3))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct QuickAnswerCard: View {
    let answer: QuickAnswer
    @State private var isEvidenceExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "sparkles").foregroundStyle(Color.accentColor)
                Text(answer.answer).font(.body)
                Spacer()
                ConfidenceBadge(confidence: answer.confidence)
            }

            DisclosureGroup(isExpanded: $isEvidenceExpanded) {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(answer.evidence) { finding in
                        FindingRow(finding: finding)
                    }
                }
                .padding(.top, 4)
            } label: {
                Text("Evidence (\(answer.evidence.count))").font(.subheadline.weight(.semibold))
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Reasoning").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                Text(answer.reasoning).font(.callout)
            }

            if !answer.missingInformation.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Missing information").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    ForEach(answer.missingInformation, id: \.self) { item in
                        Label(item, systemImage: "questionmark.circle").font(.callout)
                    }
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Recommended next question").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                Text(answer.recommendedNextQuestion).font(.callout.italic())
            }
        }
        .padding(.leading, 28)
    }
}

// FindingRow, SourceTypeBadge, ConfidenceBadge moved to FindingViews.swift —
// shared with DeepAnalysisView's Concern/Opportunity evidence disclosures.
