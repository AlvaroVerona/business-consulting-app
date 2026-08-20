import Foundation

enum SidecarError: LocalizedError {
    case server(status: Int, body: String)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .server(let status, let body): return "Sidecar returned \(status): \(body)"
        case .decoding(let error): return "Failed to decode sidecar response: \(error)"
        }
    }
}

/// Talks to the local Python sidecar (FastAPI) at 127.0.0.1:8765. The sidecar
/// owns persistence, ingestion, and LLM orchestration — this client is a
/// thin HTTP wrapper, no business logic. An actor so it's safe to share as
/// a singleton across the @MainActor view models that call it.
actor SidecarClient {
    static let shared = SidecarClient()

    private let baseURL = URL(string: "http://127.0.0.1:8765")!
    private let session = URLSession(configuration: .default)
    private let decoder = SidecarJSON.decoder
    private let encoder = SidecarJSON.encoder

    private init() {}

    // MARK: - health

    /// Used by SidecarLauncher to decide whether it needs to spawn the
    /// sidecar process at all (it may already be running — started
    /// manually, or by an earlier launch of this app that's still up).
    /// Deliberately returns Bool rather than throwing: a connection refused
    /// is the expected, common case here, not an error to report.
    func isHealthy() async -> Bool {
        var request = URLRequest(url: baseURL.appendingPathComponent("/health"))
        request.httpMethod = "GET"
        request.timeoutInterval = 1.5

        guard let (_, response) = try? await session.data(for: request) else { return false }
        return (response as? HTTPURLResponse)?.statusCode == 200
    }

    // MARK: - companies / projects

    func listCompanies() async throws -> [Company] {
        try await get("/companies")
    }

    func createCompany(_ payload: CompanyCreate) async throws -> Company {
        try await post("/companies", body: payload)
    }

    func listProjects(companyId: Int) async throws -> [Project] {
        try await get("/companies/\(companyId)/projects")
    }

    func createProject(companyId: Int, payload: ProjectCreate) async throws -> Project {
        try await post("/companies/\(companyId)/projects", body: payload)
    }

    // MARK: - documents

    func listDocuments(projectId: Int) async throws -> [BusinessDocument] {
        try await get("/projects/\(projectId)/documents")
    }

    func uploadDocument(projectId: Int, filename: String, mimeType: String, data: Data) async throws -> BusinessDocument {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: baseURL.appendingPathComponent("/projects/\(projectId)/documents"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        return try await send(request)
    }

    /// The original uploaded bytes (not the parsed/chunked text) — used for
    /// an in-app preview via macOS Quick Look, which already knows how to
    /// render PDF/CSV/DOCX/MD/XLSX without this app needing its own
    /// per-file-type renderer.
    func downloadDocumentContent(projectId: Int, documentId: Int) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent("/projects/\(projectId)/documents/\(documentId)/content"))
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw SidecarError.server(status: http.statusCode, body: String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }

    // MARK: - findings / chat

    func listFindings(projectId: Int) async throws -> [Finding] {
        try await get("/projects/\(projectId)/findings")
    }

    /// `timeoutInterval` overrides here (and on runDeepAnalysis/createIssueTree
    /// below) exist because the session's default 60s (URLSession(configuration:
    /// .default)'s timeoutIntervalForRequest) isn't enough for these three
    /// specifically — every other call is a fast CRUD op or deterministic
    /// computation, but these hit a local Ollama model with its own retry
    /// loop (up to 3 generation attempts server-side on a parse/validation
    /// failure) and can additionally need to wait for Ollama to cold-start
    /// the model if it was idle. Reproduced live: a Quick Answer question hit
    /// exactly this combination (one retry + a model that had just spun back
    /// up) and the 60s default timed out client-side while the sidecar was
    /// still legitimately working — confirmed by the sidecar's own log
    /// showing no timeout on its end (it has none talking to Ollama) and the
    /// request eventually would have succeeded.
    func askQuickQuestion(projectId: Int, question: String, useClaude: Bool = false) async throws -> QuickAnswer {
        try await post(
            "/projects/\(projectId)/chat",
            body: ChatRequest(question: question, useClaude: useClaude),
            timeoutInterval: 120
        )
    }

    // MARK: - concerns / opportunities / hypotheses

    func detectConcerns(projectId: Int) async throws -> [Concern] {
        try await post("/projects/\(projectId)/concerns/detect", body: EmptyBody())
    }

    func listConcerns(projectId: Int) async throws -> [Concern] {
        try await get("/projects/\(projectId)/concerns")
    }

    func detectOpportunities(projectId: Int) async throws -> [Opportunity] {
        try await post("/projects/\(projectId)/opportunities/detect", body: EmptyBody())
    }

    func listOpportunities(projectId: Int) async throws -> [Opportunity] {
        try await get("/projects/\(projectId)/opportunities")
    }

    func listHypotheses(projectId: Int) async throws -> [Hypothesis] {
        try await get("/projects/\(projectId)/hypotheses")
    }

    // MARK: - business understanding / deep analysis

    func getBusinessProfile(projectId: Int) async throws -> BusinessProfile? {
        try await get("/projects/\(projectId)/business-profile")
    }

    /// Longest timeout of the three (see askQuickQuestion's doc comment for
    /// why these need one at all): this runs a multi-step pipeline
    /// (BusinessUnderstandingAgent, HypothesisManagerAgent per concern,
    /// ExecutiveSynthesizerService), each with its own up-to-3-attempt retry
    /// loop — measured live at ~50s total with zero retries needed, so a
    /// single retry anywhere in the chain pushes well past 60s.
    func runDeepAnalysis(projectId: Int, useClaude: Bool = false) async throws -> DeepAnalysisRun {
        try await post(
            "/projects/\(projectId)/deep-analysis",
            body: DeepAnalysisRequest(useClaude: useClaude),
            timeoutInterval: 300
        )
    }

    func listDeepAnalysisRuns(projectId: Int) async throws -> [DeepAnalysisRun] {
        try await get("/projects/\(projectId)/deep-analysis")
    }

    // MARK: - financial analysis / reports

    func runFinancialAnalysis(projectId: Int) async throws -> FinancialAnalysis {
        try await post("/projects/\(projectId)/analysis/financial", body: EmptyBody())
    }

    enum ReportFormat: String {
        case pdf, pptx, excel

        var pathExtension: String {
            switch self {
            case .pdf: return "pdf"
            case .pptx: return "pptx"
            case .excel: return "xlsx"
            }
        }
    }

    func downloadReport(projectId: Int, format: ReportFormat) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent("/projects/\(projectId)/reports/\(format.rawValue)"))
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw SidecarError.server(status: http.statusCode, body: String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }

    // MARK: - scenario modeling / monitoring

    func runScenario(projectId: Int, request: ScenarioRequest) async throws -> ScenarioResult {
        try await post("/projects/\(projectId)/scenarios", body: request)
    }

    func listMonitoringEvents(projectId: Int) async throws -> [MonitoringEvent] {
        try await get("/projects/\(projectId)/monitoring/events")
    }

    // MARK: - issue trees

    /// See askQuickQuestion's doc comment for why this needs a longer
    /// timeout than the session default.
    func createIssueTree(projectId: Int, question: String, useClaude: Bool = false) async throws -> IssueTree {
        try await post(
            "/projects/\(projectId)/issue-trees",
            body: IssueTreeRequest(question: question, useClaude: useClaude),
            timeoutInterval: 120
        )
    }

    func listIssueTrees(projectId: Int) async throws -> [IssueTree] {
        try await get("/projects/\(projectId)/issue-trees")
    }

    // MARK: - plumbing

    private struct EmptyBody: Encodable {}

    private func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"
        return try await send(request)
    }

    private func post<Body: Encodable, T: Decodable>(
        _ path: String, body: Body, timeoutInterval: TimeInterval? = nil
    ) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        if let timeoutInterval { request.timeoutInterval = timeoutInterval }
        return try await send(request)
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)

        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw SidecarError.server(status: http.statusCode, body: String(data: data, encoding: .utf8) ?? "")
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw SidecarError.decoding(error)
        }
    }
}
