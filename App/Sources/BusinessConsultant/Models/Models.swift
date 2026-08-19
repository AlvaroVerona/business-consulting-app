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
