@testable import BusinessConsultant
import XCTest

@MainActor
final class AppViewModelTests: XCTestCase {
    func testLoadCompaniesFetchesProjectsForEachCompany() async {
        let fake = FakeSidecarClient()
        await fake.setListCompaniesHandler { [Fixtures.company(id: 1, name: "Acme"), Fixtures.company(id: 2, name: "Globex")] }
        await fake.setListProjectsHandler { companyId in
            [Fixtures.project(id: companyId * 100, companyId: companyId)]
        }

        let vm = AppViewModel(client: fake)
        await vm.loadCompanies()

        XCTAssertEqual(vm.companies.map(\.id), [1, 2])
        XCTAssertEqual(vm.projectsByCompany[1]?.map(\.id), [100])
        XCTAssertEqual(vm.projectsByCompany[2]?.map(\.id), [200])
        XCTAssertNil(vm.errorMessage)
    }

    func testLoadCompaniesFailureSetsErrorMessage() async {
        struct Boom: LocalizedError { var errorDescription: String? { "sidecar unreachable" } }
        let fake = FakeSidecarClient()
        await fake.setListCompaniesHandler { throw Boom() }

        let vm = AppViewModel(client: fake)
        await vm.loadCompanies()

        XCTAssertEqual(vm.errorMessage, "sidecar unreachable")
        XCTAssertTrue(vm.companies.isEmpty)
    }

    func testCreateProjectInsertsAtFrontAndSelectsIt() async {
        let fake = FakeSidecarClient()
        await fake.setCreateProjectHandler { companyId, payload in
            Fixtures.project(id: 42, companyId: companyId, name: payload.name)
        }

        let vm = AppViewModel(client: fake)
        vm.projectsByCompany[1] = [Fixtures.project(id: 1, companyId: 1, name: "Older")]

        await vm.createProject(companyId: 1, name: "New Engagement", description: nil)

        XCTAssertEqual(vm.projectsByCompany[1]?.map(\.name), ["New Engagement", "Older"])
        XCTAssertEqual(vm.selectedProject?.name, "New Engagement")
    }
}

private extension FakeSidecarClient {
    func setListCompaniesHandler(_ handler: @escaping @Sendable () async throws -> [Company]) {
        listCompaniesHandler = handler
    }

    func setListProjectsHandler(_ handler: @escaping @Sendable (Int) async throws -> [Project]) {
        listProjectsHandler = handler
    }

    func setCreateProjectHandler(_ handler: @escaping @Sendable (Int, ProjectCreate) async throws -> Project) {
        createProjectHandler = handler
    }
}
