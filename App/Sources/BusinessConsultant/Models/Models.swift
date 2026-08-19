import Foundation

struct Company: Codable, Identifiable, Hashable {
    let id: Int
    var name: String
    var industry: String?
    var notes: String?
    let createdAt: Date
}

struct Project: Codable, Identifiable, Hashable {
    let id: Int
    let companyId: Int
    var name: String
    var description: String?
    let createdAt: Date
}

struct BusinessDocument: Codable, Identifiable, Hashable {
    let id: Int
    let projectId: Int
    var filename: String
    var fileType: String
    var status: String
    var error: String?
    let createdAt: Date
}

/// Spec section 5: every conclusion the app states must be tagged as one of these.
enum SourceType: String, Codable, CaseIterable {
    case fact = "FACT"
    case calculation = "CALCULATION"
    case inference = "INFERENCE"
    case hypothesis = "HYPOTHESIS"
    case assumption = "ASSUMPTION"

    var label: String {
        switch self {
        case .fact: return "Fact"
        case .calculation: return "Calculation"
        case .inference: return "Inference"
        case .hypothesis: return "Hypothesis"
        case .assumption: return "Assumption"
        }
    }
}

/// Deliberately coarse (spec section 10: avoid fake precision) rather than a
/// numeric score.
enum Confidence: String, Codable, CaseIterable {
    case high = "HIGH"
    case medium = "MEDIUM"
    case low = "LOW"
    case unknown = "UNKNOWN"
}

struct Citation: Codable, Hashable {
    var documentId: Int?
    var chunkId: Int?
    var location: JSONValue?
}

struct Finding: Codable, Identifiable, Hashable {
    let id: Int
    var statement: String
    var sourceType: SourceType
    var confidence: Confidence
    var citation: Citation
    var calculation: String?
    var assumption: String?
    /// "engine" (deterministic Python arithmetic) or "llm". See DISCOVERY.md's
    /// 2026-08-19 note on a real arithmetic error caught in an LLM-computed finding.
    var origin: String?
}

struct ChatRequest: Codable {
    var question: String
    var useClaude: Bool = false
}

struct QuickAnswer: Codable {
    var answer: String
    var evidence: [Finding]
    var reasoning: String
    var confidence: Confidence
    var missingInformation: [String]
    var recommendedNextQuestion: String
}

struct CompanyCreate: Codable {
    var name: String
    var industry: String?
    var notes: String?
}

struct ProjectCreate: Codable {
    var name: String
    var description: String?
}

// MARK: - Phase 2/3: analysis engine

enum Severity: String, Codable {
    case low = "LOW"
    case medium = "MEDIUM"
    case high = "HIGH"
    case critical = "CRITICAL"
}

struct Concern: Codable, Identifiable, Hashable {
    let id: Int
    var projectId: Int
    var title: String
    var severity: Severity
    var evidenceFindingIds: [Int]
    var businessImpact: String?
    var rootCauseHypothesisIds: [Int]
    var confidence: Confidence
    var whatWouldChangeConclusion: String?
    var recommendedAction: String?
    let createdAt: Date
}

struct Opportunity: Codable, Identifiable, Hashable {
    let id: Int
    var projectId: Int
    var title: String
    var rationale: String
    var evidenceFindingIds: [Int]
    var estimatedValue: String?
    var requiredCapabilities: String?
    var risks: String?
    var confidence: Confidence
    var nextStep: String?
    let createdAt: Date
}

enum HypothesisStatus: String, Codable, CaseIterable {
    case confirmed = "CONFIRMED"
    case stronglySupported = "STRONGLY_SUPPORTED"
    case plausible = "PLAUSIBLE"
    case inconclusive = "INCONCLUSIVE"
    case weak = "WEAK"
    case contradicted = "CONTRADICTED"
}

struct Hypothesis: Codable, Identifiable, Hashable {
    let id: Int
    var projectId: Int
    var statement: String
    var status: HypothesisStatus
    var origin: String?
    var supportingFindingIds: [Int]
    var contradictingFindingIds: [Int]
    var dataRequired: String?
    var businessImpact: String?
    var priority: String?
    var nextTest: String?
    let createdAt: Date
    let updatedAt: Date
}

struct BusinessProfile: Codable, Identifiable, Hashable {
    let id: Int
    var projectId: Int
    var businessModel: String?
    var productsServices: String?
    var customers: String?
    var geographies: String?
    var revenueStreams: String?
    var costStructure: String?
    var valueProposition: String?
    var distributionModel: String?
    var competitivePosition: String?
    var keyCapabilities: String?
    var strategicObjectives: String?
    var missingInformation: [String]
    var confidence: Confidence
    var findingIds: [Int]
    let createdAt: Date
}

struct BusinessPerformanceSummary: Codable, Hashable {
    var revenue: String
    var growth: String
    var margin: String
    var cash: String
    var keyOperationalMetrics: [String]
}

struct StrategicOption: Codable, Hashable, Identifiable {
    var id: String { option }
    var option: String
    var upside: String
    var downside: String
    var investment: String
    var feasibility: Confidence
    var risks: String
    var recommendation: String
}

struct ActionPlanItem: Codable, Hashable, Identifiable {
    var id: String { action }
    var action: String
    var dataRequirements: String?
    var decisionNeeded: String?
    var kpi: String?
    var expectedImpact: String?
}

struct ExecutiveSynthesis: Codable, Hashable {
    var overallAssessment: String
    var keyFindings: [String]
    var concernIds: [Int]
    var opportunityIds: [Int]
    var businessPerformance: BusinessPerformanceSummary
    var strategicOptions: [StrategicOption]
    var ninetyDayPlan: [ActionPlanItem]
    var missingInformation: [String]
}

struct QualityIssue: Codable, Hashable, Identifiable {
    var id: String { "\(entityType)-\(entityId)-\(issue)" }
    var entityType: String
    var entityId: Int
    var issue: String
    var detail: String
}

struct DeepAnalysisRun: Codable, Identifiable, Hashable {
    let id: Int
    var projectId: Int
    var status: String
    var error: String?
    var executiveSummary: ExecutiveSynthesis?
    var qualityIssues: [QualityIssue]
    let createdAt: Date
    var completedAt: Date?
}

struct DeepAnalysisRequest: Codable {
    var useClaude: Bool = false
}

// MARK: - Phase 4: financial analysis / reports

struct PeriodMetrics: Codable, Hashable, Identifiable {
    var id: String { period }
    var period: String
    var revenue: Double?
    var cogs: Double?
    var opex: Double?
    var ebitda: Double?
    var ebitdaIsImplied: Bool
    var grossMargin: Double?
    var ebitdaMargin: Double?
    var opexRatio: Double?
}

struct FinancialAnalysis: Codable, Hashable {
    var periods: [PeriodMetrics]
    var revenueTrend: String?
    var grossMarginTrend: String?
    var ebitdaMarginTrend: String?
    var findings: [Finding]
}

// MARK: - Phase 5: scenario modeling / monitoring

enum ScenarioField: String, Codable, CaseIterable {
    case revenue, cogs, opex

    var label: String {
        switch self {
        case .revenue: return "Revenue"
        case .cogs: return "COGS"
        case .opex: return "Opex"
        }
    }
}

struct ScenarioAdjustment: Codable, Hashable, Identifiable {
    let id = UUID()
    var field: ScenarioField
    var kind: String = "percent"  // this app's UI only offers percent adjustments; "absolute" exists API-side
    var value: Double  // 0.10 means "+10%"

    enum CodingKeys: String, CodingKey {
        case field, kind, value
    }
}

struct ScenarioRequest: Codable {
    var basePeriod: String?
    var adjustments: [ScenarioAdjustment]
}

struct ScenarioResult: Codable, Hashable {
    var baseline: PeriodMetrics
    var scenario: PeriodMetrics
    var revenueDelta: Double?
    var grossMarginDelta: Double?
    var ebitdaMarginDelta: Double?
}

struct MonitoringEvent: Codable, Identifiable, Hashable {
    let id: Int
    var projectId: Int
    var entityType: String
    var eventType: String
    var title: String
    var previousValue: String?
    var newValue: String?
    let createdAt: Date
}

// MARK: - Issue trees (spec section 4 / MVP DoD #6)

struct IssueNode: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    var label: String
    var isForcedMece: Bool
    var overlapNote: String?
    var children: [IssueNode]

    /// For SwiftUI's `OutlineGroup(children:)`, which expects nil (not an
    /// empty array) to mean "leaf, no disclosure triangle".
    var nonEmptyChildren: [IssueNode]? { children.isEmpty ? nil : children }
}

struct IssueTree: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    var projectId: Int
    var question: String
    var overallNote: String?
    var rootChildren: [IssueNode]
    let createdAt: Date
}

struct IssueTreeRequest: Codable {
    var question: String
    var useClaude: Bool = false
}
