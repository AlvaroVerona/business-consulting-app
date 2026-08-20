import Foundation

/// The subset of `SidecarClient` that the view models actually call, extracted
/// so tests can substitute a fake implementation instead of hitting a real
/// (or absent) sidecar process. `SidecarClient` conforms to this for free —
/// its method signatures already match.
protocol SidecarClientProtocol: Sendable {
    func listCompanies() async throws -> [Company]
    func createCompany(_ payload: CompanyCreate) async throws -> Company
    func listProjects(companyId: Int) async throws -> [Project]
    func createProject(companyId: Int, payload: ProjectCreate) async throws -> Project

    func listDocuments(projectId: Int) async throws -> [BusinessDocument]
    func uploadDocument(projectId: Int, filename: String, mimeType: String, data: Data) async throws -> BusinessDocument
    func downloadDocumentContent(projectId: Int, documentId: Int) async throws -> Data

    func listFindings(projectId: Int) async throws -> [Finding]
    func askQuickQuestion(projectId: Int, question: String, useClaude: Bool) async throws -> QuickAnswer

    func listConcerns(projectId: Int) async throws -> [Concern]
    func listOpportunities(projectId: Int) async throws -> [Opportunity]
    func listHypotheses(projectId: Int) async throws -> [Hypothesis]

    func getBusinessProfile(projectId: Int) async throws -> BusinessProfile?
    func runDeepAnalysis(projectId: Int, useClaude: Bool) async throws -> DeepAnalysisRun
    func listDeepAnalysisRuns(projectId: Int) async throws -> [DeepAnalysisRun]

    func runFinancialAnalysis(projectId: Int) async throws -> FinancialAnalysis
    func downloadReport(projectId: Int, format: SidecarClient.ReportFormat) async throws -> Data

    func runScenario(projectId: Int, request: ScenarioRequest) async throws -> ScenarioResult
    func listMonitoringEvents(projectId: Int) async throws -> [MonitoringEvent]

    func createIssueTree(projectId: Int, question: String, useClaude: Bool) async throws -> IssueTree
    func listIssueTrees(projectId: Int) async throws -> [IssueTree]
}

extension SidecarClient: SidecarClientProtocol {}
