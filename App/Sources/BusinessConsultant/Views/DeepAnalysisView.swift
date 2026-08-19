import SwiftUI

/// Spec section 11's executive output format, rendered from the latest
/// DeepAnalysisRun. Concerns/opportunities are looked up from the project's
/// full lists by the ids the synthesis referenced, so severity/confidence/
/// evidence always come from the one source of truth (the persisted rows),
/// never restated by the LLM.
struct DeepAnalysisView: View {
    @State var viewModel: ProjectViewModel
    @Environment(\.dismiss) private var dismiss

    var latestRun: DeepAnalysisRun? { viewModel.deepAnalysisRuns.first }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header

                    if let run = latestRun {
                        switch run.status {
                        case "COMPLETED":
                            if let synthesis = run.executiveSummary {
                                completedContent(synthesis)
                            }
                        case "FAILED":
                            Label(run.error ?? "Deep analysis failed.", systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.red)
                        default:
                            ProgressView("Running…")
                        }
                    } else {
                        ContentUnavailableView(
                            "No analysis yet",
                            systemImage: "chart.bar.doc.horizontal",
                            description: Text("Run a deep analysis to get a business profile, concerns, opportunities, hypotheses, and an executive synthesis.")
                        )
                    }
                }
                .padding()
            }
            .navigationTitle("Deep Analysis")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    if viewModel.isRunningDeepAnalysis {
                        ProgressView().controlSize(.small)
                    } else {
                        Button {
                            Task { await viewModel.runDeepAnalysis() }
                        } label: {
                            Label("Run", systemImage: "play.fill")
                        }
                    }
                }
            }
        }
        .frame(minWidth: 640, minHeight: 560)
    }

    private var header: some View {
        HStack {
            if let run = latestRun {
                Text("Last run: \(run.status.capitalized) · \(run.createdAt.formatted(date: .abbreviated, time: .shortened))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func completedContent(_ synthesis: ExecutiveSynthesis) -> some View {
        Section {
            Text(synthesis.overallAssessment).font(.title3)
        } header: { SectionHeader("Overall Assessment") }

        if !synthesis.keyFindings.isEmpty {
            Section {
                ForEach(synthesis.keyFindings, id: \.self) { Label($0, systemImage: "circle.fill").font(.callout) }
            } header: { SectionHeader("Key Findings") }
        }

        Section {
            BusinessPerformanceView(summary: synthesis.businessPerformance)
        } header: { SectionHeader("Business Performance") }

        let referencedConcerns = viewModel.concerns.filter { synthesis.concernIds.contains($0.id) }
        if !referencedConcerns.isEmpty {
            Section {
                ForEach(referencedConcerns) { ConcernRow(concern: $0) }
            } header: { SectionHeader("Key Concerns") }
        }

        let referencedOpportunities = viewModel.opportunities.filter { synthesis.opportunityIds.contains($0.id) }
        if !referencedOpportunities.isEmpty {
            Section {
                ForEach(referencedOpportunities) { OpportunityRow(opportunity: $0) }
            } header: { SectionHeader("Key Opportunities") }
        }

        if !viewModel.hypotheses.isEmpty {
            Section {
                ForEach(viewModel.hypotheses) { HypothesisRow(hypothesis: $0) }
            } header: { SectionHeader("Hypotheses") }
        }

        if !synthesis.strategicOptions.isEmpty {
            Section {
                ForEach(synthesis.strategicOptions) { StrategicOptionRow(option: $0) }
            } header: { SectionHeader("Strategic Options") }
        }

        if !synthesis.ninetyDayPlan.isEmpty {
            Section {
                ForEach(synthesis.ninetyDayPlan) { ActionPlanRow(item: $0) }
            } header: { SectionHeader("90-Day Action Plan") }
        }

        if !synthesis.missingInformation.isEmpty {
            Section {
                ForEach(synthesis.missingInformation, id: \.self) {
                    Label($0, systemImage: "questionmark.circle").font(.callout).foregroundStyle(.secondary)
                }
            } header: { SectionHeader("Missing Information") }
        }

        if !(latestRun?.qualityIssues.isEmpty ?? true) {
            Section {
                ForEach(latestRun!.qualityIssues) {
                    Label($0.detail, systemImage: "flag.fill").font(.caption).foregroundStyle(.orange)
                }
            } header: { SectionHeader("Quality Review Flags") }
        }
    }
}

private struct SectionHeader: View {
    let title: String
    init(_ title: String) { self.title = title }
    var body: some View {
        Text(title).font(.headline).padding(.top, 4)
    }
}

private struct BusinessPerformanceView: View {
    let summary: BusinessPerformanceSummary
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            LabeledContent("Revenue", value: summary.revenue)
            LabeledContent("Growth", value: summary.growth)
            LabeledContent("Margin", value: summary.margin)
            LabeledContent("Cash", value: summary.cash)
            ForEach(summary.keyOperationalMetrics, id: \.self) { Text("• \($0)").font(.callout) }
        }
        .font(.callout)
    }
}

private struct ConcernRow: View {
    let concern: Concern
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(concern.title).font(.body.weight(.semibold))
                SeverityBadge(severity: concern.severity)
            }
            if let impact = concern.businessImpact { Text(impact).font(.callout) }
            if let action = concern.recommendedAction {
                Text("Action: \(action)").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .background(.red.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

private struct OpportunityRow: View {
    let opportunity: Opportunity
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(opportunity.title).font(.body.weight(.semibold))
            Text(opportunity.rationale).font(.callout)
            if let next = opportunity.nextStep {
                Text("Next: \(next)").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .background(.green.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

private struct HypothesisRow: View {
    let hypothesis: Hypothesis
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(hypothesis.statement).font(.callout)
                Spacer()
                Text(hypothesis.status.rawValue.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.caption2.weight(.semibold))
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(.purple.opacity(0.15))
                    .clipShape(Capsule())
            }
            if let dataRequired = hypothesis.dataRequired {
                Text("Needs: \(dataRequired)").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .background(.purple.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

private struct StrategicOptionRow: View {
    let option: StrategicOption
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(option.option).font(.body.weight(.semibold))
            Text("Upside: \(option.upside)").font(.caption)
            Text("Downside: \(option.downside)").font(.caption)
            Text("Recommendation: \(option.recommendation)").font(.caption).foregroundStyle(.secondary)
        }
        .padding(8)
        .background(.blue.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

private struct ActionPlanRow: View {
    let item: ActionPlanItem
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(item.action).font(.callout.weight(.medium))
            if let kpi = item.kpi { Text("KPI: \(kpi)").font(.caption).foregroundStyle(.secondary) }
        }
    }
}

private struct SeverityBadge: View {
    let severity: Severity
    var color: Color {
        switch severity {
        case .low: return .yellow
        case .medium: return .orange
        case .high: return .red
        case .critical: return .red
        }
    }
    var body: some View {
        Text(severity.rawValue.capitalized)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
