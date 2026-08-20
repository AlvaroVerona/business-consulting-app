import SwiftUI

/// Spec section 15 Phase 5, Scenario Modeling — a what-if tool over the
/// deterministic financial engine (spec section 13: no LLM involved in the
/// math). Results are never persisted; they're recomputed on demand.
struct ScenarioView: View {
    @State var viewModel: ProjectViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var basePeriod: String?
    @State private var revenuePercent: Double = 0
    @State private var cogsPercent: Double = 0
    @State private var opexPercent: Double = 0

    private var latestPeriods: [PeriodMetrics] { viewModel.financialAnalysis?.periods ?? [] }

    var body: some View {
        NavigationStack {
            Form {
                if latestPeriods.isEmpty {
                    ContentUnavailableView(
                        "No financial data yet",
                        systemImage: "slider.horizontal.3",
                        description: Text("Upload a P&L and run financial analysis first.")
                    )
                } else {
                    Section("Base period") {
                        Picker("Period", selection: $basePeriod) {
                            Text("Latest (\(latestPeriods.last?.period ?? ""))").tag(String?.none)
                            ForEach(latestPeriods) { p in
                                Text(p.period).tag(String?.some(p.period))
                            }
                        }
                    }

                    Section("Adjustments") {
                        AdjustmentSlider(label: "Revenue", value: $revenuePercent)
                        AdjustmentSlider(label: "COGS", value: $cogsPercent)
                        AdjustmentSlider(label: "Opex", value: $opexPercent)
                    }

                    Section {
                        Button {
                            Task { await runScenario() }
                        } label: {
                            if viewModel.isRunningScenario {
                                ProgressView().controlSize(.small)
                            } else {
                                Text("Run Scenario")
                            }
                        }
                        .disabled(viewModel.isRunningScenario)
                    }

                    if let result = viewModel.scenarioResult {
                        Section("Result") {
                            ComparisonRow(label: "Revenue", baseline: result.baseline.revenue, scenario: result.scenario.revenue, format: .currency)
                            ComparisonRow(label: "COGS", baseline: result.baseline.cogs, scenario: result.scenario.cogs, format: .currency)
                            ComparisonRow(label: "Opex", baseline: result.baseline.opex, scenario: result.scenario.opex, format: .currency)
                            ComparisonRow(label: "Gross Margin", baseline: result.baseline.grossMargin, scenario: result.scenario.grossMargin, format: .percent)
                            ComparisonRow(label: "EBITDA Margin", baseline: result.baseline.ebitdaMargin, scenario: result.scenario.ebitdaMargin, format: .percent)
                        }
                        .textSelection(.enabled)
                    }
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Scenario Modeling")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
        .frame(minWidth: 480, minHeight: 480)
        .task { if viewModel.financialAnalysis == nil { await viewModel.loadFinancialAnalysis() } }
    }

    private func runScenario() async {
        var adjustments: [ScenarioAdjustment] = []
        if revenuePercent != 0 { adjustments.append(ScenarioAdjustment(field: .revenue, value: revenuePercent)) }
        if cogsPercent != 0 { adjustments.append(ScenarioAdjustment(field: .cogs, value: cogsPercent)) }
        if opexPercent != 0 { adjustments.append(ScenarioAdjustment(field: .opex, value: opexPercent)) }

        await viewModel.runScenario(adjustments: adjustments, basePeriod: basePeriod)
    }
}

private struct AdjustmentSlider: View {
    let label: String
    @Binding var value: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(label)
                Spacer()
                Text(value, format: .percent.sign(strategy: .always())).monospacedDigit().foregroundStyle(.secondary)
            }
            Slider(value: $value, in: -0.5...0.5, step: 0.01)
        }
    }
}

private enum ComparisonFormat {
    case currency, percent
}

private struct ComparisonRow: View {
    let label: String
    let baseline: Double?
    let scenario: Double?
    let format: ComparisonFormat

    private func text(_ value: Double?) -> String {
        guard let value else { return "—" }
        switch format {
        case .currency: return value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        case .percent: return value.formatted(.percent.precision(.fractionLength(1)))
        }
    }

    var body: some View {
        HStack {
            Text(label)
            Spacer()
            Text(text(baseline)).foregroundStyle(.secondary)
            Image(systemName: "arrow.right").font(.caption).foregroundStyle(.tertiary)
            Text(text(scenario)).fontWeight(.semibold)
        }
        .font(.callout)
    }
}
