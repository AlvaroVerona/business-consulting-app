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

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let raw = try container.decode(String.self)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: raw) { return date }

            // FastAPI/SQLite naive datetimes have no timezone suffix.
            let fallback = DateFormatter()
            fallback.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
            fallback.timeZone = TimeZone(identifier: "UTC")
            if let date = fallback.date(from: raw) { return date }

            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unrecognized date: \(raw)")
        }
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    private init() {}

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

    // MARK: - findings / chat

    func listFindings(projectId: Int) async throws -> [Finding] {
        try await get("/projects/\(projectId)/findings")
    }

    func askQuickQuestion(projectId: Int, question: String, useClaude: Bool = false) async throws -> QuickAnswer {
        try await post("/projects/\(projectId)/chat", body: ChatRequest(question: question, useClaude: useClaude))
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

    func runDeepAnalysis(projectId: Int, useClaude: Bool = false) async throws -> DeepAnalysisRun {
        try await post("/projects/\(projectId)/deep-analysis", body: DeepAnalysisRequest(useClaude: useClaude))
    }

    func listDeepAnalysisRuns(projectId: Int) async throws -> [DeepAnalysisRun] {
        try await get("/projects/\(projectId)/deep-analysis")
    }

    // MARK: - plumbing

    private struct EmptyBody: Encodable {}

    private func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"
        return try await send(request)
    }

    private func post<Body: Encodable, T: Decodable>(_ path: String, body: Body) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
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
