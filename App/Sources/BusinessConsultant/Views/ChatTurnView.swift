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

private struct FindingRow: View {
    let finding: Finding

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                SourceTypeBadge(sourceType: finding.sourceType)
                ConfidenceBadge(confidence: finding.confidence)
                if finding.origin == "engine" {
                    Label("Engine-computed", systemImage: "checkmark.seal.fill")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.teal)
                }
                Spacer()
            }

            Text(finding.statement).font(.callout)

            if let calculation = finding.calculation {
                Text("Calculation: \(calculation)").font(.caption).foregroundStyle(.secondary)
            }

            if let assumption = finding.assumption {
                Text("Assumption: \(assumption)").font(.caption).foregroundStyle(.secondary)
            }

            if finding.citation.documentId != nil || finding.citation.chunkId != nil {
                Text("Source: document #\(finding.citation.documentId.map(String.init) ?? "—"), \(finding.citation.location?.displayText ?? "chunk #\(finding.citation.chunkId.map(String.init) ?? "—")")")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(8)
        .background(.background.opacity(0.6))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

private struct SourceTypeBadge: View {
    let sourceType: SourceType

    var color: Color {
        switch sourceType {
        case .fact: return .green
        case .calculation: return .blue
        case .inference: return .purple
        case .hypothesis: return .orange
        case .assumption: return .gray
        }
    }

    var body: some View {
        Text(sourceType.label)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}

private struct ConfidenceBadge: View {
    let confidence: Confidence

    var color: Color {
        switch confidence {
        case .high: return .green
        case .medium: return .yellow
        case .low: return .orange
        case .unknown: return .secondary
        }
    }

    var body: some View {
        Text(confidence.rawValue.capitalized)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
