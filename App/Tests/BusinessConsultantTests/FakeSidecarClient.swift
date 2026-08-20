@testable import BusinessConsultant
import Foundation

/// Test double for `SidecarClientProtocol`. Each method is backed by an
/// optional handler closure the test sets before exercising a view model;
/// calling an unstubbed method throws `NotStubbed` rather than hitting the
/// network, so a test that forgets to stub something fails loudly instead of
/// hanging or silently talking to a real sidecar.
actor FakeSidecarClient: SidecarClientProtocol {
    struct NotStubbed: Error {
        let method: String
    }

    var listCompaniesHandler: (@Sendable () async throws -> [Company])?
    var createCompanyHandler: (@Sendable (CompanyCreate) async throws -> Company)?
    var listProjectsHandler: (@Sendable (Int) async throws -> [Project])?
    var createProjectHandler: (@Sendable (Int, ProjectCreate) async throws -> Project)?

    var listDocumentsHandler: (@Sendable (Int) async throws -> [BusinessDocument])?
    var uploadDocumentHandler: (@Sendable (Int, String, String, Data) async throws -> BusinessDocument)?

    var listFindingsHandler: (@Sendable (Int) async throws -> [Finding])?
    var askQuickQuestionHandler: (@Sendable (Int, String, Bool) async throws -> QuickAnswer)?

    var listConcernsHandler: (@Sendable (Int) async throws -> [Concern])?
    var listOpportunitiesHandler: (@Sendable (Int) async throws -> [Opportunity])?
    var listHypothesesHandler: (@Sendable (Int) async throws -> [Hypothesis])?

    var getBusinessProfileHandler: (@Sendable (Int) async throws -> BusinessProfile?)?
    var runDeepAnalysisHandler: (@Sendable (Int, Bool) async throws -> DeepAnalysisRun)?
    var listDeepAnalysisRunsHandler: (@Sendable (Int) async throws -> [DeepAnalysisRun])?

    var runFinancialAnalysisHandler: (@Sendable (Int) async throws -> FinancialAnalysis)?
    var downloadReportHandler: (@Sendable (Int, SidecarClient.ReportFormat) async throws -> Data)?

    var runScenarioHandler: (@Sendable (Int, ScenarioRequest) async throws -> ScenarioResult)?
    var listMonitoringEventsHandler: (@Sendable (Int) async throws -> [MonitoringEvent])?

    var createIssueTreeHandler: (@Sendable (Int, String, Bool) async throws -> IssueTree)?
    var listIssueTreesHandler: (@Sendable (Int) async throws -> [IssueTree])?

    private(set) var createIssueTreeCallCount = 0
    private(set) var askQuickQuestionCallCount = 0

    func listCompanies() async throws -> [Company] {
        guard let handler = listCompaniesHandler else { throw NotStubbed(method: "listCompanies") }
        return try await handler()
    }

    func createCompany(_ payload: CompanyCreate) async throws -> Company {
        guard let handler = createCompanyHandler else { throw NotStubbed(method: "createCompany") }
        return try await handler(payload)
    }

    func listProjects(companyId: Int) async throws -> [Project] {
        guard let handler = listProjectsHandler else { throw NotStubbed(method: "listProjects") }
        return try await handler(companyId)
    }

    func createProject(companyId: Int, payload: ProjectCreate) async throws -> Project {
        guard let handler = createProjectHandler else { throw NotStubbed(method: "createProject") }
        return try await handler(companyId, payload)
    }

    func listDocuments(projectId: Int) async throws -> [BusinessDocument] {
        guard let handler = listDocumentsHandler else { throw NotStubbed(method: "listDocuments") }
        return try await handler(projectId)
    }

    func uploadDocument(projectId: Int, filename: String, mimeType: String, data: Data) async throws -> BusinessDocument {
        guard let handler = uploadDocumentHandler else { throw NotStubbed(method: "uploadDocument") }
        return try await handler(projectId, filename, mimeType, data)
    }

    func listFindings(projectId: Int) async throws -> [Finding] {
        guard let handler = listFindingsHandler else { throw NotStubbed(method: "listFindings") }
        return try await handler(projectId)
    }

    func askQuickQuestion(projectId: Int, question: String, useClaude: Bool) async throws -> QuickAnswer {
        askQuickQuestionCallCount += 1
        guard let handler = askQuickQuestionHandler else { throw NotStubbed(method: "askQuickQuestion") }
        return try await handler(projectId, question, useClaude)
    }

    func listConcerns(projectId: Int) async throws -> [Concern] {
        guard let handler = listConcernsHandler else { throw NotStubbed(method: "listConcerns") }
        return try await handler(projectId)
    }

    func listOpportunities(projectId: Int) async throws -> [Opportunity] {
        guard let handler = listOpportunitiesHandler else { throw NotStubbed(method: "listOpportunities") }
        return try await handler(projectId)
    }

    func listHypotheses(projectId: Int) async throws -> [Hypothesis] {
        guard let handler = listHypothesesHandler else { throw NotStubbed(method: "listHypotheses") }
        return try await handler(projectId)
    }

    func getBusinessProfile(projectId: Int) async throws -> BusinessProfile? {
        guard let handler = getBusinessProfileHandler else { throw NotStubbed(method: "getBusinessProfile") }
        return try await handler(projectId)
    }

    func runDeepAnalysis(projectId: Int, useClaude: Bool) async throws -> DeepAnalysisRun {
        guard let handler = runDeepAnalysisHandler else { throw NotStubbed(method: "runDeepAnalysis") }
        return try await handler(projectId, useClaude)
    }

    func listDeepAnalysisRuns(projectId: Int) async throws -> [DeepAnalysisRun] {
        guard let handler = listDeepAnalysisRunsHandler else { throw NotStubbed(method: "listDeepAnalysisRuns") }
        return try await handler(projectId)
    }

    func runFinancialAnalysis(projectId: Int) async throws -> FinancialAnalysis {
        guard let handler = runFinancialAnalysisHandler else { throw NotStubbed(method: "runFinancialAnalysis") }
        return try await handler(projectId)
    }

    func downloadReport(projectId: Int, format: SidecarClient.ReportFormat) async throws -> Data {
        guard let handler = downloadReportHandler else { throw NotStubbed(method: "downloadReport") }
        return try await handler(projectId, format)
    }

    func runScenario(projectId: Int, request: ScenarioRequest) async throws -> ScenarioResult {
        guard let handler = runScenarioHandler else { throw NotStubbed(method: "runScenario") }
        return try await handler(projectId, request)
    }

    func listMonitoringEvents(projectId: Int) async throws -> [MonitoringEvent] {
        guard let handler = listMonitoringEventsHandler else { throw NotStubbed(method: "listMonitoringEvents") }
        return try await handler(projectId)
    }

    func createIssueTree(projectId: Int, question: String, useClaude: Bool) async throws -> IssueTree {
        createIssueTreeCallCount += 1
        guard let handler = createIssueTreeHandler else { throw NotStubbed(method: "createIssueTree") }
        return try await handler(projectId, question, useClaude)
    }

    func listIssueTrees(projectId: Int) async throws -> [IssueTree] {
        guard let handler = listIssueTreesHandler else { throw NotStubbed(method: "listIssueTrees") }
        return try await handler(projectId)
    }
}
