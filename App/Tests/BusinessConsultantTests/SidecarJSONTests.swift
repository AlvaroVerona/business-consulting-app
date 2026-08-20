@testable import BusinessConsultant
import XCTest

/// `SidecarJSON` is the wire contract with the Python sidecar: snake_case
/// keys and two different date formats (see its doc comment). These are
/// tested against fixture JSON shaped exactly like FastAPI's actual output,
/// not just round-tripped through Swift's own encoder, so a change to either
/// side's field names or date format is caught here instead of only at
/// runtime against a live sidecar.
final class SidecarJSONTests: XCTestCase {
    func testDecodesSnakeCaseFinding() throws {
        let json = """
        {
            "id": 42,
            "statement": "Gross margin was 60%.",
            "source_type": "CALCULATION",
            "confidence": "HIGH",
            "citation": {"document_id": 3, "chunk_id": 9, "location": null},
            "calculation": null,
            "assumption": null,
            "origin": "engine"
        }
        """.data(using: .utf8)!

        let finding = try SidecarJSON.decoder.decode(Finding.self, from: json)

        XCTAssertEqual(finding.id, 42)
        XCTAssertEqual(finding.sourceType, .calculation)
        XCTAssertEqual(finding.citation.chunkId, 9)
        XCTAssertEqual(finding.citation.documentId, 3)
        XCTAssertEqual(finding.origin, "engine")
    }

    func testDecodesConcernWithArrayFields() throws {
        let json = """
        {
            "id": 1,
            "project_id": 7,
            "title": "Margin compression",
            "severity": "HIGH",
            "evidence_finding_ids": [1, 2, 3],
            "business_impact": null,
            "root_cause_hypothesis_ids": [10],
            "confidence": "MEDIUM",
            "what_would_change_conclusion": null,
            "recommended_action": "Investigate input costs.",
            "created_at": "2026-08-19T10:15:30.123456"
        }
        """.data(using: .utf8)!

        let concern = try SidecarJSON.decoder.decode(Concern.self, from: json)

        XCTAssertEqual(concern.projectId, 7)
        XCTAssertEqual(concern.evidenceFindingIds, [1, 2, 3])
        XCTAssertEqual(concern.rootCauseHypothesisIds, [10])
        XCTAssertEqual(concern.recommendedAction, "Investigate input costs.")
    }

    /// FastAPI/SQLite naive datetimes (no timezone suffix) — the fallback
    /// format `SidecarJSON.decoder` added specifically for this case.
    func testDecodesNaiveSQLiteDatetime() throws {
        let json = """
        {"id": 1, "name": "Acme", "industry": null, "notes": null, "created_at": "2026-08-19T10:15:30.123456"}
        """.data(using: .utf8)!

        let company = try SidecarJSON.decoder.decode(Company.self, from: json)

        var expected = DateComponents()
        expected.year = 2026; expected.month = 8; expected.day = 19
        expected.hour = 10; expected.minute = 15; expected.second = 30
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        let expectedDate = calendar.date(from: expected)!

        XCTAssertEqual(company.createdAt.timeIntervalSince1970, expectedDate.timeIntervalSince1970, accuracy: 1)
    }

    /// Timezone-aware ISO8601 with fractional seconds — the primary format.
    func testDecodesTimezoneAwareISO8601Datetime() throws {
        let json = """
        {"id": 1, "name": "Acme", "industry": null, "notes": null, "created_at": "2026-08-19T10:15:30.123Z"}
        """.data(using: .utf8)!

        let company = try SidecarJSON.decoder.decode(Company.self, from: json)
        XCTAssertNotNil(company.createdAt)
    }

    func testUnrecognizedDateFormatThrows() {
        let json = """
        {"id": 1, "name": "Acme", "industry": null, "notes": null, "created_at": "not-a-date"}
        """.data(using: .utf8)!

        XCTAssertThrowsError(try SidecarJSON.decoder.decode(Company.self, from: json))
    }

    /// Recursive structure — IssueNode nests IssueNode via `children`. A
    /// regression in the self-referential decode would silently drop or
    /// misplace deeper tree levels.
    func testDecodesNestedIssueTree() throws {
        let json = """
        {
            "id": 1,
            "project_id": 1,
            "question": "Why did EBITDA decline?",
            "overall_note": null,
            "root_children": [
                {
                    "id": 1,
                    "label": "Revenue Mix",
                    "is_forced_mece": false,
                    "overlap_note": null,
                    "children": [
                        {"id": 2, "label": "Price", "is_forced_mece": false, "overlap_note": null, "children": []},
                        {"id": 3, "label": "Volume", "is_forced_mece": true, "overlap_note": "Bundled with Mix", "children": []}
                    ]
                }
            ],
            "created_at": "2026-08-19T10:15:30.123456"
        }
        """.data(using: .utf8)!

        let tree = try SidecarJSON.decoder.decode(IssueTree.self, from: json)

        XCTAssertEqual(tree.rootChildren.count, 1)
        let root = tree.rootChildren[0]
        XCTAssertEqual(root.children.count, 2)
        XCTAssertEqual(root.children[1].isForcedMece, true)
        XCTAssertEqual(root.children[1].overlapNote, "Bundled with Mix")
    }

    /// The encoder side of the same contract: outgoing requests must use
    /// snake_case so FastAPI/Pydantic accept them.
    func testEncodesToSnakeCase() throws {
        let request = ScenarioRequest(
            basePeriod: "2026-01",
            adjustments: [ScenarioAdjustment(field: .revenue, value: 0.1)]
        )

        let data = try SidecarJSON.encoder.encode(request)
        let obj = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(obj["base_period"] as? String, "2026-01")
        let adjustments = obj["adjustments"] as! [[String: Any]]
        XCTAssertEqual(adjustments[0]["field"] as? String, "revenue")
        XCTAssertEqual(adjustments[0]["value"] as? Double, 0.1)
    }
}
