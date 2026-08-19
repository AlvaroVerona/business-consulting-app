import Charts
import SwiftUI

/// Spec section 15 Phase 4, "executive dashboards" — a native visual summary
/// of the deterministic financial engine's output (spec section 13: this
/// data is never LLM-computed) plus concern/opportunity counts.
struct DashboardView: View {
    @State var viewModel: ProjectViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let analysis = viewModel.financialAnalysis, !analysis.periods.isEmpty {
                        summaryCards
                        revenueChart(analysis)
                        marginChart(analysis)
                    } else {
                        ContentUnavailableView(
                            "No financial data yet",
                            systemImage: "chart.line.uptrend.xyaxis",
                            description: Text("Upload a P&L (CSV or XLSX with period/revenue/cogs columns) and run the financial analysis.")
                        )
                    }
                }
                .padding()
            }
            .navigationTitle("Dashboard")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await viewModel.loadFinancialAnalysis() }
                    } label: {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }
                }
            }
        }
        .frame(minWidth: 640, minHeight: 560)
        .task { await viewModel.loadFinancialAnalysis() }
    }

    private var summaryCards: some View {
        HStack(spacing: 12) {
            StatCard(title: "Concerns", value: "\(viewModel.concerns.count)", color: .red)
            StatCard(title: "Opportunities", value: "\(viewModel.opportunities.count)", color: .green)
            StatCard(title: "Hypotheses", value: "\(viewModel.hypotheses.count)", color: .purple)
        }
    }

    private func revenueChart(_ analysis: FinancialAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Revenue").font(.headline)
                if let trend = analysis.revenueTrend { TrendBadge(trend: trend) }
            }
            Chart(analysis.periods) { period in
                if let revenue = period.revenue {
                    LineMark(x: .value("Period", period.period), y: .value("Revenue", revenue))
                    PointMark(x: .value("Period", period.period), y: .value("Revenue", revenue))
                }
            }
            .frame(height: 180)
        }
    }

    private func marginChart(_ analysis: FinancialAnalysis) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Margins").font(.headline)
                if let trend = analysis.grossMarginTrend { TrendBadge(trend: trend, label: "Gross") }
            }
            Chart(analysis.periods) { period in
                if let margin = period.grossMargin {
                    LineMark(x: .value("Period", period.period), y: .value("Gross Margin", margin))
                        .foregroundStyle(by: .value("Series", "Gross Margin"))
                }
                if let margin = period.ebitdaMargin {
                    LineMark(x: .value("Period", period.period), y: .value("EBITDA Margin", margin))
                        .foregroundStyle(by: .value("Series", "EBITDA Margin"))
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisValueLabel {
                        if let percent = value.as(Double.self) {
                            Text(percent, format: .percent)
                        }
                    }
                }
            }
            .frame(height: 180)
        }
    }
}

private struct StatCard: View {
    let title: String
    let value: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value).font(.title.bold())
            Text(title).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(color.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

private struct TrendBadge: View {
    let trend: String
    var label: String? = nil

    var color: Color {
        switch trend {
        case "improving": return .green
        case "declining": return .red
        case "stable": return .secondary
        default: return .orange
        }
    }

    var icon: String {
        switch trend {
        case "improving": return "arrow.up.right"
        case "declining": return "arrow.down.right"
        case "stable": return "arrow.right"
        default: return "arrow.left.arrow.right"
        }
    }

    var body: some View {
        Label((label.map { "\($0): " } ?? "") + trend.capitalized, systemImage: icon)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
