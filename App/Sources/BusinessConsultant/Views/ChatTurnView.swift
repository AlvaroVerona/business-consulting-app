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

            // Best-effort, not guaranteed — a local model doesn't always
            // produce one even when asked to (see quick_answer_service.py's
            // PROMPT_TEMPLATE comment). Hiding the section entirely when
            // empty avoids showing a "Recommended next question" header
            // with nothing under it, which read as the app having broken.
            // Trimmed, not a raw .isEmpty check — a whitespace-only value
            // (a model under pressure not to send "" could send " "
            // instead) would pass a raw check but still render as blank.
            let trimmedNextQuestion = answer.recommendedNextQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmedNextQuestion.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Recommended next question").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    Text(trimmedNextQuestion).font(.callout.italic())
                }
            }
        }
        .padding(.leading, 28)
    }
}

// FindingRow, SourceTypeBadge, ConfidenceBadge moved to FindingViews.swift —
// shared with DeepAnalysisView's Concern/Opportunity evidence disclosures.
