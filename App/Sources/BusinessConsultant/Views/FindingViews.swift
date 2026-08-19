import SwiftUI

/// Shared by ChatTurnView (a Quick Answer's evidence list) and
/// DeepAnalysisView (a Concern/Opportunity's evidence_finding_ids) — one
/// rendering of "why was this concluded" so the two don't drift.
struct FindingRow: View {
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

struct SourceTypeBadge: View {
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

struct ConfidenceBadge: View {
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

/// A concern/opportunity's evidence_finding_ids resolved against the
/// project's full finding list and rendered as a disclosure — spec section
/// 12: "an evidence panel so the user can inspect exactly why an AI
/// conclusion was generated," which previously existed only for Quick
/// Answer's evidence, not for Concerns/Opportunities despite them carrying
/// the same evidence_finding_ids link.
struct EvidenceDisclosure: View {
    let findingIds: [Int]
    let allFindings: [Finding]
    @State private var isExpanded = false

    private var resolved: [Finding] {
        let byId = Dictionary(uniqueKeysWithValues: allFindings.map { ($0.id, $0) })
        return findingIds.compactMap { byId[$0] }
    }

    var body: some View {
        if !findingIds.isEmpty {
            DisclosureGroup(isExpanded: $isExpanded) {
                VStack(alignment: .leading, spacing: 6) {
                    if resolved.isEmpty {
                        Text("Findings not loaded yet.").font(.caption).foregroundStyle(.secondary)
                    } else {
                        ForEach(resolved) { FindingRow(finding: $0) }
                    }
                }
                .padding(.top, 4)
            } label: {
                Text("Evidence (\(findingIds.count))").font(.caption.weight(.semibold))
            }
        }
    }
}
