import AppKit
import Foundation

@MainActor
@Observable
final class AppViewModel {
    var companies: [Company] = []
    var projectsByCompany: [Int: [Project]] = [:]
    var selectedProject: Project?
    var errorMessage: String?

    private let client = SidecarClient.shared

    func loadCompanies() async {
        do {
            companies = try await client.listCompanies()
            for company in companies {
                await loadProjects(for: company)
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func loadProjects(for company: Company) async {
        do {
            projectsByCompany[company.id] = try await client.listProjects(companyId: company.id)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func createCompany(name: String, industry: String?) async {
        do {
            let company = try await client.createCompany(CompanyCreate(name: name, industry: industry, notes: nil))
            companies.insert(company, at: 0)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func createProject(companyId: Int, name: String, description: String?) async {
        do {
            let project = try await client.createProject(
                companyId: companyId,
                payload: ProjectCreate(name: name, description: description)
            )
            projectsByCompany[companyId, default: []].insert(project, at: 0)
            selectedProject = project
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct ChatTurn: Identifiable {
    let id = UUID()
    let question: String
    var answer: QuickAnswer?
    var errorMessage: String?
}

@MainActor
@Observable
final class ProjectViewModel {
    let project: Project

    var documents: [BusinessDocument] = []
    var turns: [ChatTurn] = []
    var pendingQuestion: String = ""
    var isAsking = false
    var isUploading = false
    var errorMessage: String?

    var concerns: [Concern] = []
    var opportunities: [Opportunity] = []
    var hypotheses: [Hypothesis] = []
    var findings: [Finding] = []
    var businessProfile: BusinessProfile?
    var deepAnalysisRuns: [DeepAnalysisRun] = []
    var isRunningDeepAnalysis = false

    var financialAnalysis: FinancialAnalysis?
    var isExportingReport = false

    var monitoringEvents: [MonitoringEvent] = []
    var scenarioResult: ScenarioResult?
    var isRunningScenario = false

    var issueTrees: [IssueTree] = []
    var pendingIssueTreeQuestion: String = ""
    var isBuildingIssueTree = false

    private let client = SidecarClient.shared

    init(project: Project) {
        self.project = project
    }

    func load() async {
        do {
            // These 9 reads are independent — running them concurrently
            // instead of one-after-another saves 8 round-trips' worth of
            // latency on every workspace load.
            async let documentsTask = client.listDocuments(projectId: project.id)
            async let concernsTask = client.listConcerns(projectId: project.id)
            async let opportunitiesTask = client.listOpportunities(projectId: project.id)
            async let hypothesesTask = client.listHypotheses(projectId: project.id)
            async let findingsTask = client.listFindings(projectId: project.id)
            async let businessProfileTask = client.getBusinessProfile(projectId: project.id)
            async let deepAnalysisRunsTask = client.listDeepAnalysisRuns(projectId: project.id)
            async let monitoringEventsTask = client.listMonitoringEvents(projectId: project.id)
            async let issueTreesTask = client.listIssueTrees(projectId: project.id)

            (documents, concerns, opportunities, hypotheses, findings, businessProfile, deepAnalysisRuns, monitoringEvents, issueTrees) =
                try await (
                    documentsTask, concernsTask, opportunitiesTask, hypothesesTask, findingsTask,
                    businessProfileTask, deepAnalysisRunsTask, monitoringEventsTask, issueTreesTask
                )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func runScenario(adjustments: [ScenarioAdjustment], basePeriod: String? = nil) async {
        isRunningScenario = true
        defer { isRunningScenario = false }

        do {
            scenarioResult = try await client.runScenario(
                projectId: project.id,
                request: ScenarioRequest(basePeriod: basePeriod, adjustments: adjustments)
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func buildIssueTree(useClaude: Bool = false) async {
        guard !isBuildingIssueTree else { return }  // TextField stays enabled while in flight; block a duplicate submit

        let question = pendingIssueTreeQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty else { return }

        isBuildingIssueTree = true
        defer { isBuildingIssueTree = false }

        do {
            let tree = try await client.createIssueTree(projectId: project.id, question: question, useClaude: useClaude)
            issueTrees.insert(tree, at: 0)
            pendingIssueTreeQuestion = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func runDeepAnalysis(useClaude: Bool = false) async {
        isRunningDeepAnalysis = true
        defer { isRunningDeepAnalysis = false }

        do {
            _ = try await client.runDeepAnalysis(projectId: project.id, useClaude: useClaude)
            // The run persists new/updated concerns, opportunities, hypotheses,
            // a business profile, and itself as a side effect — one reload
            // picks up all of it from the authoritative server state.
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func loadFinancialAnalysis() async {
        do {
            financialAnalysis = try await client.runFinancialAnalysis(projectId: project.id)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func exportReport(format: SidecarClient.ReportFormat) async {
        isExportingReport = true
        defer { isExportingReport = false }

        do {
            let data = try await client.downloadReport(projectId: project.id, format: format)

            let panel = NSSavePanel()
            panel.nameFieldStringValue = "\(project.name)_report.\(format.pathExtension)"
            panel.canCreateDirectories = true

            guard panel.runModal() == .OK, let url = panel.url else { return }
            try data.write(to: url)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func upload(fileURL: URL) async {
        isUploading = true
        defer { isUploading = false }

        do {
            let data = try Data(contentsOf: fileURL)
            let mimeType = mimeType(for: fileURL.pathExtension)
            let document = try await client.uploadDocument(
                projectId: project.id,
                filename: fileURL.lastPathComponent,
                mimeType: mimeType,
                data: data
            )
            documents.insert(document, at: 0)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func ask() async {
        let question = pendingQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty else { return }

        pendingQuestion = ""
        isAsking = true
        defer { isAsking = false }

        var turn = ChatTurn(question: question)
        turns.append(turn)
        let index = turns.count - 1

        do {
            let answer = try await client.askQuickQuestion(projectId: project.id, question: question)
            turn.answer = answer
        } catch {
            turn.errorMessage = error.localizedDescription
        }

        turns[index] = turn
    }

    private func mimeType(for pathExtension: String) -> String {
        switch pathExtension.lowercased() {
        case "pdf": return "application/pdf"
        case "csv": return "text/csv"
        case "docx": return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        case "xlsx": return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        case "md": return "text/markdown"
        default: return "text/plain"
        }
    }
}
