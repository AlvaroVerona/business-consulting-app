@testable import BusinessConsultant
import XCTest

@MainActor
final class ProjectViewModelTests: XCTestCase {
    // MARK: - ask()

    func testAskIgnoresBlankQuestion() async {
        let fake = FakeSidecarClient()
        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        vm.pendingQuestion = "   "

        await vm.ask()

        XCTAssertTrue(vm.turns.isEmpty)
        let calls = await fake.askQuickQuestionCallCount
        XCTAssertEqual(calls, 0)
    }

    func testAskSuccessAppendsAnsweredTurn() async {
        let fake = FakeSidecarClient()
        await fake.setAskQuickQuestionHandler { _, question, _ in
            XCTAssertEqual(question, "What drove the margin change?")
            return Fixtures.quickAnswer(answer: "Input costs rose.")
        }
        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        vm.pendingQuestion = "  What drove the margin change?  "

        await vm.ask()

        XCTAssertEqual(vm.turns.count, 1)
        XCTAssertEqual(vm.turns[0].answer?.answer, "Input costs rose.")
        XCTAssertNil(vm.turns[0].errorMessage)
        XCTAssertEqual(vm.pendingQuestion, "", "the input field should clear once the question is submitted")
    }

    func testAskFailureRecordsErrorOnTheTurnNotJustGlobally() async {
        struct Boom: LocalizedError { var errorDescription: String? { "sidecar unreachable" } }
        let fake = FakeSidecarClient()
        await fake.setAskQuickQuestionHandler { _, _, _ in throw Boom() }
        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        vm.pendingQuestion = "Why?"

        await vm.ask()

        XCTAssertEqual(vm.turns.count, 1)
        XCTAssertNil(vm.turns[0].answer)
        XCTAssertEqual(vm.turns[0].errorMessage, "sidecar unreachable")
    }

    // MARK: - buildIssueTree()

    func testBuildIssueTreeIgnoresBlankQuestion() async {
        let fake = FakeSidecarClient()
        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        vm.pendingIssueTreeQuestion = "   "

        await vm.buildIssueTree()

        let calls = await fake.createIssueTreeCallCount
        XCTAssertEqual(calls, 0)
    }

    /// Regression test for the duplicate-submit bug fixed during the issue
    /// trees pass: the TextField stays enabled while a build is in flight,
    /// so a second Return press must be a no-op, not a second POST.
    func testBuildIssueTreeGuardsAgainstReentrantSubmit() async {
        let fake = FakeSidecarClient()
        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        vm.pendingIssueTreeQuestion = "Why did EBITDA decline?"
        vm.isBuildingIssueTree = true // simulates "a build is already in flight"

        await vm.buildIssueTree()

        let calls = await fake.createIssueTreeCallCount
        XCTAssertEqual(calls, 0, "a build already in flight must block a second submit")
        XCTAssertEqual(vm.pendingIssueTreeQuestion, "Why did EBITDA decline?", "the guarded call must not consume the pending question")
    }

    func testBuildIssueTreeSuccessInsertsAtFrontAndClearsInput() async {
        let fake = FakeSidecarClient()
        await fake.setCreateIssueTreeHandler { _, question, _ in Fixtures.issueTree(question: question) }
        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        vm.issueTrees = [Fixtures.issueTree(id: 99, question: "Older question")]
        vm.pendingIssueTreeQuestion = "Why did EBITDA decline?"

        await vm.buildIssueTree()

        XCTAssertEqual(vm.issueTrees.count, 2)
        XCTAssertEqual(vm.issueTrees[0].question, "Why did EBITDA decline?")
        XCTAssertEqual(vm.pendingIssueTreeQuestion, "")
        XCTAssertFalse(vm.isBuildingIssueTree)
    }

    // MARK: - load()

    /// `load()` fires 9 concurrent requests and destructures them into 9
    /// properties by tuple position (ViewModels.swift). Every field happens
    /// to have a distinct Swift type, so the compiler already rejects most
    /// position swaps — but not a same-typed mixup like accidentally wiring
    /// `documentsTask` to the wrong array-of-BusinessDocument field, and not
    /// a call to the wrong client method with a type-compatible return. This
    /// exercises the real end-to-end wiring rather than relying on that
    /// compile-time safety net alone.
    func testLoadAssignsEachConcurrentResultToTheRightProperty() async {
        let fake = FakeSidecarClient()
        await fake.setListDocumentsHandler { _ in [Fixtures.businessDocument(id: 1)] }
        await fake.setListConcernsHandler { _ in [Fixtures.concern(id: 2)] }
        await fake.setListOpportunitiesHandler { _ in [Fixtures.opportunity(id: 3)] }
        await fake.setListHypothesesHandler { _ in [Fixtures.hypothesis(id: 4)] }
        await fake.setListFindingsHandler { _ in [Fixtures.finding(id: 5)] }
        await fake.setGetBusinessProfileHandler { _ in Fixtures.businessProfile(id: 6) }
        await fake.setListDeepAnalysisRunsHandler { _ in [Fixtures.deepAnalysisRun(id: 7)] }
        await fake.setListMonitoringEventsHandler { _ in [Fixtures.monitoringEvent(id: 8)] }
        await fake.setListIssueTreesHandler { _ in [Fixtures.issueTree(id: 9)] }

        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        await vm.load()

        XCTAssertEqual(vm.documents.map(\.id), [1])
        XCTAssertEqual(vm.concerns.map(\.id), [2])
        XCTAssertEqual(vm.opportunities.map(\.id), [3])
        XCTAssertEqual(vm.hypotheses.map(\.id), [4])
        XCTAssertEqual(vm.findings.map(\.id), [5])
        XCTAssertEqual(vm.businessProfile?.id, 6)
        XCTAssertEqual(vm.deepAnalysisRuns.map(\.id), [7])
        XCTAssertEqual(vm.monitoringEvents.map(\.id), [8])
        XCTAssertEqual(vm.issueTrees.map(\.id), [9])
        XCTAssertNil(vm.errorMessage)
    }

    func testLoadFailureSetsErrorMessage() async {
        struct Boom: LocalizedError { var errorDescription: String? { "network down" } }
        let fake = FakeSidecarClient()
        await fake.setListDocumentsHandler { _ in throw Boom() }
        // The other 8 handlers stay unstubbed too (they'll throw NotStubbed),
        // but `documentsTask` is first in `load()`'s tuple destructure, so
        // its error is the one that propagates out of the `try await`.

        let vm = ProjectViewModel(project: Fixtures.project(), client: fake)
        await vm.load()

        XCTAssertEqual(vm.errorMessage, "network down")
    }
}

private extension FakeSidecarClient {
    func setAskQuickQuestionHandler(_ handler: @escaping @Sendable (Int, String, Bool) async throws -> QuickAnswer) {
        askQuickQuestionHandler = handler
    }

    func setCreateIssueTreeHandler(_ handler: @escaping @Sendable (Int, String, Bool) async throws -> IssueTree) {
        createIssueTreeHandler = handler
    }

    func setListDocumentsHandler(_ handler: @escaping @Sendable (Int) async throws -> [BusinessDocument]) {
        listDocumentsHandler = handler
    }

    func setListConcernsHandler(_ handler: @escaping @Sendable (Int) async throws -> [Concern]) {
        listConcernsHandler = handler
    }

    func setListOpportunitiesHandler(_ handler: @escaping @Sendable (Int) async throws -> [Opportunity]) {
        listOpportunitiesHandler = handler
    }

    func setListHypothesesHandler(_ handler: @escaping @Sendable (Int) async throws -> [Hypothesis]) {
        listHypothesesHandler = handler
    }

    func setListFindingsHandler(_ handler: @escaping @Sendable (Int) async throws -> [Finding]) {
        listFindingsHandler = handler
    }

    func setGetBusinessProfileHandler(_ handler: @escaping @Sendable (Int) async throws -> BusinessProfile?) {
        getBusinessProfileHandler = handler
    }

    func setListDeepAnalysisRunsHandler(_ handler: @escaping @Sendable (Int) async throws -> [DeepAnalysisRun]) {
        listDeepAnalysisRunsHandler = handler
    }

    func setListMonitoringEventsHandler(_ handler: @escaping @Sendable (Int) async throws -> [MonitoringEvent]) {
        listMonitoringEventsHandler = handler
    }

    func setListIssueTreesHandler(_ handler: @escaping @Sendable (Int) async throws -> [IssueTree]) {
        listIssueTreesHandler = handler
    }
}
