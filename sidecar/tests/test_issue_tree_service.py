import json

import pytest

from src.database.repository import Repository
from src.services.issue_tree_service import IssueTreeService


class FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.responses.pop(0)


def _valid_response() -> str:
    return json.dumps(
        {
            "root_children": [
                {
                    "label": "Revenue",
                    "is_forced_mece": False,
                    "overlap_note": None,
                    "children": [
                        {"label": "Price", "is_forced_mece": False, "overlap_note": None, "children": []},
                        {"label": "Volume", "is_forced_mece": False, "overlap_note": None, "children": []},
                        {
                            "label": "Mix",
                            "is_forced_mece": True,
                            "overlap_note": "Bundled promotions blur mix and price effects.",
                            "children": [],
                        },
                    ],
                },
                {
                    "label": "Costs",
                    "is_forced_mece": False,
                    "overlap_note": None,
                    "children": [
                        {"label": "COGS", "is_forced_mece": False, "overlap_note": None, "children": []},
                        {"label": "SG&A", "is_forced_mece": False, "overlap_note": None, "children": []},
                    ],
                },
            ],
            "overall_note": None,
        }
    )


def _seed_project(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    return repo, project.id


def test_persists_full_tree_structure(db_session):
    repo, project_id = _seed_project(db_session)

    llm = FakeLLM([_valid_response()])
    tree = IssueTreeService(repo, llm).run(project_id, "Why did EBITDA decline?")

    assert tree.question == "Why did EBITDA decline?"
    nodes = repo.list_issue_nodes(tree.id)
    assert len(nodes) == 7  # 2 top-level + 3 + 2 sub-branches

    roots = [n for n in nodes if n.parent_id is None]
    assert {n.label for n in roots} == {"Revenue", "Costs"}

    revenue = next(n for n in roots if n.label == "Revenue")
    revenue_children = [n for n in nodes if n.parent_id == revenue.id]
    assert {n.label for n in revenue_children} == {"Price", "Volume", "Mix"}

    mix = next(n for n in revenue_children if n.label == "Mix")
    assert mix.is_forced_mece is True
    assert mix.overlap_note is not None


def test_retries_on_excessive_depth(db_session):
    repo, project_id = _seed_project(db_session)

    too_deep = json.dumps(
        {
            "root_children": [
                {
                    "label": "A",
                    "is_forced_mece": False,
                    "overlap_note": None,
                    "children": [
                        {
                            "label": "B",
                            "is_forced_mece": False,
                            "overlap_note": None,
                            "children": [{"label": "C", "is_forced_mece": False, "overlap_note": None, "children": []}],
                        }
                    ],
                }
            ],
            "overall_note": None,
        }
    )

    llm = FakeLLM([too_deep, _valid_response()])
    tree = IssueTreeService(repo, llm).run(project_id, "Why did EBITDA decline?")

    assert llm.calls == 2
    assert len(repo.list_issue_nodes(tree.id)) == 7


def test_raises_after_exhausting_retries(db_session):
    repo, project_id = _seed_project(db_session)

    llm = FakeLLM(["not json"] * 10)

    with pytest.raises(ValueError):
        IssueTreeService(repo, llm).run(project_id, "Why did EBITDA decline?")


def test_retries_on_excessive_branching(db_session):
    """Regression: only depth was validated, never sibling count — a model
    returning e.g. 20 top-level branches passed straight through."""
    repo, project_id = _seed_project(db_session)

    too_wide = json.dumps(
        {
            "root_children": [
                {"label": f"Branch {i}", "is_forced_mece": False, "overlap_note": None, "children": []}
                for i in range(20)
            ],
            "overall_note": None,
        }
    )

    llm = FakeLLM([too_wide, _valid_response()])
    tree = IssueTreeService(repo, llm).run(project_id, "Why did EBITDA decline?")

    assert llm.calls == 2
    assert len(repo.list_issue_nodes(tree.id)) == 7


def test_persistence_failure_leaves_no_truncated_tree(db_session, monkeypatch):
    """Regression: create_issue_tree/create_issue_node used to commit per
    row, so a failure partway through persistence left a permanently
    truncated tree durably saved with no way to detect or repair it. Now
    only Repository.commit() (called once, at the very end) makes anything
    durable — simulate a failure on the 2nd node and confirm nothing at all
    was persisted."""
    repo, project_id = _seed_project(db_session)

    real_create_issue_node = repo.create_issue_node
    call_count = {"n": 0}

    def flaky_create_issue_node(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated failure")
        return real_create_issue_node(*args, **kwargs)

    monkeypatch.setattr(repo, "create_issue_node", flaky_create_issue_node)

    llm = FakeLLM([_valid_response()])
    with pytest.raises(RuntimeError):
        IssueTreeService(repo, llm).run(project_id, "Why did EBITDA decline?")

    assert repo.list_issue_trees(project_id) == []
