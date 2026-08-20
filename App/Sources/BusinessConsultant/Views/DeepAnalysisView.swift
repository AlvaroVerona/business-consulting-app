import SwiftUI

/// Spec section 11's executive output format. Concerns/opportunities/
/// hypotheses are always shown from the project's full, backend-prioritized
/// lists (repository.py sorts by severity/confidence) — never filtered down
/// to only what the executive synthesis happened to reference. A concern the
/// deterministic engine detected but the LLM's synthesis didn't mention is
/// still a real, evidence-grounded concern; hiding it behind the LLM's
/// summarization choice would violate the evidence-integrity principle this
/// app is built around. Rows the synthesis *did* reference get a small
/// "Highlighted" badge instead.
struct DeepAnalysisView: View {
    @State var viewModel: ProjectViewModel
    @Environment(\.dismiss) private var dismiss

    var latestRun: DeepAnalysisRun? { viewModel.deepAnalysisRuns.first }
    var synthesis: ExecutiveSynthesis? { latestRun?.status == "COMPLETED" ? latestRun?.executiveSummary : nil }

    private var hasAnyData: Bool {
        !viewModel.concerns.isEmpty || !viewModel.opportunities.isEmpty || !viewModel.hypotheses.isEmpty || latestRun != nil
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header

                    if let run = latestRun, run.status == "FAILED" {
                        Label(run.error ?? "Deep analysis failed.", systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                    } else if let run = latestRun, run.status == "RUNNING" {
                        ProgressView("Running…")
                    }

                    if let synthesis {
                        synthesisSummary(synthesis)
                    }

                    if !viewModel.concerns.isEmpty {
                        Section {
                            ForEach(viewModel.concerns) { concern in
                                ConcernRow(
                                    concern: concern,
                                    isHighlighted: synthesis?.concernIds.contains(concern.id) ?? false,
                                    allFindings: viewModel.findings
                                )
                            }
                        } header: { SectionHeader("Key Concerns") }
                    }

                    if !viewModel.opportunities.isEmpty {
                        Section {
                            ForEach(viewModel.opportunities) { opportunity in
                                OpportunityRow(
                                    opportunity: opportunity,
                                    isHighlighted: synthesis?.opportunityIds.contains(opportunity.id) ?? false,
                                    allFindings: viewModel.findings
                                )
                            }
                        } header: { SectionHeader("Key Opportunities") }
                    }

                    if !viewModel.hypotheses.isEmpty {
                        Section {
                            ForEach(viewModel.hypotheses) { HypothesisRow(hypothesis: $0) }
                        } header: { SectionHeader("Hypotheses") }
                    }

                    if let synthesis {
                        synthesisDetails(synthesis)
                    }

                    if !hasAnyData {
                        ContentUnavailableView(
                            "No analysis yet",
                            systemImage: "chart.bar.doc.horizontal",
                            description: Text("Run a deep analysis to get a business profile, concerns, opportunities, hypotheses, and an executive synthesis.")
                        )
                    }
                }
                .padding()
                .textSelection(.enabled)
            }
            .navigationTitle("Deep Analysis")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    if viewModel.isExportingReport {
                        ProgressView().controlSize(.small)
                    } else {
                        Menu {
                            Button("Export PDF…") { Task { await viewModel.exportReport(format: .pdf) } }
                            Button("Export PowerPoint…") { Task { await viewModel.exportReport(format: .pptx) } }
                            Button("Export Excel…") { Task { await viewModel.exportReport(format: .excel) } }
                        } label: {
                            Label("Export", systemImage: "square.and.arrow.up")
                        }
                    }
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
    private func synthesisSummary(_ synthesis: ExecutiveSynthesis) -> some View {
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
    }

    @ViewBuilder
    private func synthesisDetails(_ synthesis: ExecutiveSynthesis) -> some View {
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

private struct HighlightedBadge: View {
    var body: some View {
        Label("Highlighted", systemImage: "star.fill")
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(Color.accentColor.opacity(0.15))
            .foregroundStyle(Color.accentColor)
            .clipShape(Capsule())
    }
}

private struct ConcernRow: View {
    let concern: Concern
    let isHighlighted: Bool
    let allFindings: [Finding]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(concern.title).font(.body.weight(.semibold))
                SeverityBadge(severity: concern.severity)
                if isHighlighted { HighlightedBadge() }
            }
            if let impact = concern.businessImpact { Text(impact).font(.callout) }
            if let action = concern.recommendedAction {
                Text("Action: \(action)").font(.caption).foregroundStyle(.secondary)
            }
            EvidenceDisclosure(findingIds: concern.evidenceFindingIds, allFindings: allFindings)
        }
        .padding(8)
        .background(.red.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

private struct OpportunityRow: View {
    let opportunity: Opportunity
    let isHighlighted: Bool
    let allFindings: [Finding]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(opportunity.title).font(.body.weight(.semibold))
                if isHighlighted { HighlightedBadge() }
            }
            Text(opportunity.rationale).font(.callout)
            if let next = opportunity.nextStep {
                Text("Next: \(next)").font(.caption).foregroundStyle(.secondary)
            }
            EvidenceDisclosure(findingIds: opportunity.evidenceFindingIds, allFindings: allFindings)
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
