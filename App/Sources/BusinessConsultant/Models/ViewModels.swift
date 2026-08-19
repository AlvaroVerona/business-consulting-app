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

    private let client = SidecarClient.shared

    init(project: Project) {
        self.project = project
    }

    func load() async {
        do {
            documents = try await client.listDocuments(projectId: project.id)
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
