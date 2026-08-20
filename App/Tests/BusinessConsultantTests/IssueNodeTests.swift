@testable import BusinessConsultant
import XCTest

/// `nonEmptyChildren` exists specifically because `OutlineGroup(children:)`
/// treats nil (not an empty array) as "leaf, no disclosure triangle" — an
/// empty `[IssueNode]` would render a triangle that opens onto nothing.
final class IssueNodeTests: XCTestCase {
    func testLeafNodeHasNilNonEmptyChildren() {
        let leaf = Fixtures.issueNode(children: [])
        XCTAssertNil(leaf.nonEmptyChildren)
    }

    func testParentNodeExposesItsChildren() {
        let child = Fixtures.issueNode(id: 2, label: "Price")
        let parent = Fixtures.issueNode(id: 1, label: "Revenue Mix", children: [child])

        XCTAssertEqual(parent.nonEmptyChildren?.count, 1)
        XCTAssertEqual(parent.nonEmptyChildren?.first?.label, "Price")
    }
}
