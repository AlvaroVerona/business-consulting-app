from src.database.models import IssueTree
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.llm.retry import generate_json_with_retry
from src.schemas.issue_tree import IssueNodeDraft, IssueTreeDraft

MAX_RETRIES = 2
MAX_DEPTH = 2  # matches the spec's own example (Revenue -> Price/Volume/Mix): deep enough to be useful, shallow enough for a local model to hold together
# Generous ceiling above the prompt's stated 2-5/4 guidance — not meant to
# enforce the prompt's exact numbers (a model returning 6 top-level branches
# isn't a real problem), only to catch genuinely degenerate output (e.g. 20
# branches) that the depth check alone can't, since it only measures depth.
MAX_SIBLINGS = 8

PROMPT_TEMPLATE = """You are a strategy consultant building an issue tree (spec section 4) to
decompose a business question into a structure for investigation — not a set of conclusions.

QUESTION:
{question}

RULES:
- Return ONLY JSON. No markdown, no prose outside the JSON.
- 2-5 top-level branches. Each branch may have up to 4 sub-branches, {max_depth} levels total.
  Only go a second level where it adds real analytical value — a single-level branch is fine.
- Branches should be mutually exclusive and collectively exhaustive (MECE) WHERE THAT HOLDS.
  Do NOT force a MECE split where the business reality doesn't support one. If two branches could
  genuinely overlap (e.g. a bundled promotion affects both "Price" and "Product Mix"), set
  "is_forced_mece": true on that branch and explain the overlap in "overlap_note". Most branches
  should NOT need this — only set it where there's a real, specific overlap or gap you can name.
- Labels name what to investigate ("Price realization"), not an assertion of what happened
  ("Prices were cut too much") — this is a map for the investigation, not its findings.

{error_block}

FORMAT EXACTLY:
{{
  "root_children": [
    {{
      "label": "string",
      "is_forced_mece": false,
      "overlap_note": null,
      "children": [
        {{"label": "string", "is_forced_mece": false, "overlap_note": null, "children": []}}
      ]
    }}
  ],
  "overall_note": "string | null"
}}
"""


class IssueTreeService:
    """Spec section 4 (Issue Trees) / section 2 Deep Analysis mode step 4.
    Standalone and user-question-driven — NOT auto-triggered from a detected
    Concern, since step 3 of that same workflow ("define the key question")
    is a deliberate step of its own; guessing a question from a concern
    title would produce a weaker tree than one the user means to investigate."""

    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def run(self, project_id: int, question: str) -> IssueTree:
        draft = self._generate(question)

        # One commit for the whole tree (repo.create_issue_tree/create_issue_node
        # only flush): if persistence fails partway through, roll back so
        # nothing here is durably saved rather than leaving a truncated tree
        # behind. A flushed-but-uncommitted row is still visible to queries
        # on this same session, so skipping commit() alone isn't enough.
        try:
            tree = self.repo.create_issue_tree(project_id=project_id, question=question, overall_note=draft.overall_note)
            self._persist_nodes(tree.id, draft.root_children, parent_id=None)
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise

        return tree

    def _generate(self, question: str) -> IssueTreeDraft:
        def parse(data: dict) -> IssueTreeDraft:
            draft = IssueTreeDraft(**data)
            self._validate_depth(draft.root_children, depth=1)
            self._validate_branching(draft.root_children)
            return draft

        return generate_json_with_retry(
            self.llm,
            label="IssueTree",
            max_retries=MAX_RETRIES,
            build_prompt=lambda error_block: PROMPT_TEMPLATE.format(
                question=question, max_depth=MAX_DEPTH, error_block=error_block
            ),
            parse=parse,
        )

    @staticmethod
    def _validate_depth(nodes: list[IssueNodeDraft], depth: int) -> None:
        # Guard on non-empty first: a leaf's empty `children: []` recurses to
        # depth+1 with nothing in it, which must not itself count as
        # exceeding the limit — only an actual node at too great a depth does.
        if not nodes:
            return
        if depth > MAX_DEPTH:
            raise ValueError(f"Tree exceeds the {MAX_DEPTH}-level limit — flatten deeper branches.")
        for node in nodes:
            IssueTreeService._validate_depth(node.children, depth + 1)

    @staticmethod
    def _validate_branching(nodes: list[IssueNodeDraft]) -> None:
        if len(nodes) > MAX_SIBLINGS:
            raise ValueError(f"{len(nodes)} branches at one level exceeds the {MAX_SIBLINGS}-branch limit — consolidate.")
        for node in nodes:
            IssueTreeService._validate_branching(node.children)

    def _persist_nodes(self, tree_id: int, nodes: list[IssueNodeDraft], parent_id: int | None) -> None:
        for i, node in enumerate(nodes):
            row = self.repo.create_issue_node(
                tree_id=tree_id,
                parent_id=parent_id,
                label=node.label,
                order_index=i,
                is_forced_mece=node.is_forced_mece,
                overlap_note=node.overlap_note,
            )
            self._persist_nodes(tree_id, node.children, parent_id=row.id)
