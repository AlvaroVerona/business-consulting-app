@testable import BusinessConsultant
import Foundation

/// Minimal-but-valid instances of every model used across the test target,
/// so individual tests only spell out the fields they actually care about.
enum Fixtures {
    static func company(id: Int = 1, name: String = "Acme") -> Company {
        Company(id: id, name: name, industry: nil, notes: nil, createdAt: Date())
    }

    static func project(id: Int = 1, companyId: Int = 1, name: String = "Q1 Review") -> Project {
        Project(id: id, companyId: companyId, name: name, description: nil, createdAt: Date())
    }

    static func citation(chunkId: Int = 1, documentId: Int = 1) -> Citation {
        Citation(documentId: documentId, chunkId: chunkId, location: nil)
    }

    static func finding(id: Int = 1, statement: String = "Gross margin was 60%.") -> Finding {
        Finding(
            id: id,
            statement: statement,
            sourceType: .calculation,
            confidence: .high,
            citation: citation(),
            calculation: nil,
            assumption: nil,
            origin: "engine"
        )
    }

    static func quickAnswer(answer: String = "Margin improved.") -> QuickAnswer {
        QuickAnswer(
            answer: answer,
            evidence: [finding()],
            reasoning: "Because the numbers say so.",
            confidence: .high,
            missingInformation: [],
            recommendedNextQuestion: "What drove the change?"
        )
    }

    static func businessDocument(id: Int = 1, projectId: Int = 1) -> BusinessDocument {
        BusinessDocument(id: id, projectId: projectId, filename: "memo.pdf", fileType: "pdf", status: "processed", error: nil, createdAt: Date())
    }

    static func concern(id: Int = 1, projectId: Int = 1, title: String = "Margin compression") -> Concern {
        Concern(
            id: id,
            projectId: projectId,
            title: title,
            severity: .high,
            evidenceFindingIds: [1],
            businessImpact: nil,
            rootCauseHypothesisIds: [],
            confidence: .medium,
            whatWouldChangeConclusion: nil,
            recommendedAction: nil,
            createdAt: Date()
        )
    }

    static func opportunity(id: Int = 1, projectId: Int = 1, title: String = "Opex efficiency") -> Opportunity {
        Opportunity(
            id: id,
            projectId: projectId,
            title: title,
            rationale: "Opex ratio is above peer benchmark.",
            evidenceFindingIds: [1],
            estimatedValue: nil,
            requiredCapabilities: nil,
            risks: nil,
            confidence: .medium,
            nextStep: nil,
            createdAt: Date()
        )
    }

    static func hypothesis(id: Int = 1, projectId: Int = 1) -> Hypothesis {
        Hypothesis(
            id: id,
            projectId: projectId,
            statement: "Margin compression is driven by input cost inflation.",
            status: .plausible,
            origin: "agent",
            supportingFindingIds: [1],
            contradictingFindingIds: [],
            dataRequired: nil,
            businessImpact: nil,
            priority: nil,
            nextTest: nil,
            createdAt: Date(),
            updatedAt: Date()
        )
    }

    static func businessProfile(id: Int = 1, projectId: Int = 1) -> BusinessProfile {
        BusinessProfile(
            id: id,
            projectId: projectId,
            businessModel: "B2B SaaS",
            productsServices: nil,
            customers: nil,
            geographies: nil,
            revenueStreams: nil,
            costStructure: nil,
            valueProposition: nil,
            distributionModel: nil,
            competitivePosition: nil,
            keyCapabilities: nil,
            strategicObjectives: nil,
            missingInformation: [],
            confidence: .medium,
            findingIds: [],
            createdAt: Date()
        )
    }

    static func deepAnalysisRun(id: Int = 1, projectId: Int = 1, status: String = "COMPLETED") -> DeepAnalysisRun {
        DeepAnalysisRun(
            id: id,
            projectId: projectId,
            status: status,
            error: nil,
            executiveSummary: nil,
            qualityIssues: [],
            createdAt: Date(),
            completedAt: nil
        )
    }

    static func monitoringEvent(id: Int = 1, projectId: Int = 1) -> MonitoringEvent {
        MonitoringEvent(
            id: id,
            projectId: projectId,
            entityType: "concern",
            eventType: "new",
            title: "Margin compression",
            previousValue: nil,
            newValue: nil,
            createdAt: Date()
        )
    }

    static func issueNode(id: Int = 1, label: String = "Price Realization", children: [IssueNode] = []) -> IssueNode {
        IssueNode(id: id, label: label, isForcedMece: false, overlapNote: nil, children: children)
    }

    static func issueTree(id: Int = 1, projectId: Int = 1, question: String = "Why did EBITDA decline?") -> IssueTree {
        IssueTree(
            id: id,
            projectId: projectId,
            question: question,
            overallNote: nil,
            rootChildren: [issueNode()],
            createdAt: Date()
        )
    }

    static func financialAnalysis() -> FinancialAnalysis {
        FinancialAnalysis(periods: [], revenueTrend: nil, grossMarginTrend: nil, ebitdaMarginTrend: nil, findings: [])
    }

    static func periodMetrics(period: String = "2026-01") -> PeriodMetrics {
        PeriodMetrics(
            period: period,
            revenue: 100_000,
            cogs: 40_000,
            opex: 30_000,
            ebitda: 30_000,
            ebitdaIsImplied: false,
            grossMargin: 0.6,
            ebitdaMargin: 0.3,
            opexRatio: 0.3
        )
    }

    static func scenarioResult() -> ScenarioResult {
        ScenarioResult(
            baseline: periodMetrics(),
            scenario: periodMetrics(),
            revenueDelta: 0,
            grossMarginDelta: 0,
            ebitdaMarginDelta: 0
        )
    }
}
