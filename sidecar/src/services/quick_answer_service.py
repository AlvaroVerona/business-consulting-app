from src.database.models import Finding
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.llm.retry import generate_json_with_retry
from src.schemas.chat import QuickAnswer, QuickAnswerDraft
from src.schemas.evidence import Citation, FindingOut
from src.services.context_builder import MAX_CONTEXT_CHUNKS, build_chunk_context
from src.services.evidence_validation import validate_evidence_citations

MAX_RETRIES = 2

PROMPT_TEMPLATE = """You are a strategy-consulting-inspired business analyst. Answer the
question using ONLY the evidence provided below. Never invent numbers, documents, or
citations that are not in the evidence context.

RULES:
- Return ONLY JSON. No markdown, no prose outside the JSON.
- Every item in "evidence" must be one of: FACT, CALCULATION, INFERENCE, HYPOTHESIS, ASSUMPTION.
  - FACT: directly stated in a chunk below. Its citation MUST use that chunk's real chunk_id
    and document_id exactly as given.
  - CALCULATION: derived by you from FACTs. Fill "calculation" with the arithmetic you did.
    Citation may reference the FACT chunk(s) it used.
  - INFERENCE: a reasonable conclusion from the evidence, not stated directly. citation.chunk_id
    may be null.
  - HYPOTHESIS: a possible explanation that still needs validation. citation.chunk_id may be null.
  - ASSUMPTION: explicitly introduced because the data is not available. Fill "assumption" with
    what you assumed and why. citation.chunk_id MUST be null.
- Do NOT invent a chunk_id or document_id. Only use the ones listed in EVIDENCE CONTEXT below,
  or leave citation.chunk_id / citation.document_id null.
- If the evidence context is empty or insufficient to answer, say so plainly in "answer" and
  list what's missing in "missing_information" — do not fabricate an answer.
- Use HIGH/MEDIUM/LOW/UNKNOWN for confidence — never a numeric percentage.
- ALREADY-COMPUTED FINDINGS below were computed by deterministic code, not a language model —
  they are more reliable than arithmetic you do yourself. If one answers part of the question,
  reuse its exact number and cite the same chunk_id/document_id rather than recomputing it.

EVIDENCE CONTEXT (each item: chunk_id, document_id, filename, location, content):
{context}

ALREADY-COMPUTED FINDINGS (deterministic, trustworthy — reuse rather than recompute):
{prior_findings}

QUESTION:
{question}

{error_block}

FORMAT EXACTLY:
{{
  "answer": "string, answer-first, 2-4 sentences",
  "evidence": [
    {{
      "statement": "string",
      "source_type": "FACT" | "CALCULATION" | "INFERENCE" | "HYPOTHESIS" | "ASSUMPTION",
      "confidence": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
      "citation": {{"document_id": int | null, "chunk_id": int | null, "location": object | null}},
      "calculation": "string | null",
      "assumption": "string | null"
    }}
  ],
  "reasoning": "string, how the evidence leads to the answer",
  "confidence": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
  "missing_information": ["string"],
  "recommended_next_question": "string"
}}
"""


def _build_prior_findings_context(findings: list[Finding]) -> str:
    # Only findings from a deterministic engine (origin="engine") are worth
    # surfacing here — reusing an earlier LLM-generated CALCULATION would
    # just propagate whatever arithmetic error it already made.
    engine_findings = [f for f in findings if f.origin == "engine"]

    if not engine_findings:
        return "(none yet — run financial analysis for this project to populate this)"

    # Deliberately omits the Finding's own id: it's not a citable chunk_id,
    # and listing it next to chunk_id/document_id invites the LLM to conflate
    # the two (reproduced live: it cited a finding_id as a citation.chunk_id).
    lines = []
    for f in engine_findings[:MAX_CONTEXT_CHUNKS]:
        lines.append(
            f"- statement={f.statement}"
            + (f" calculation={f.calculation}" if f.calculation else "")
            + f" | if you cite this, use citation.chunk_id={f.chunk_id} citation.document_id={f.document_id}"
        )

    return "\n".join(lines)


class QuickAnswerService:
    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def answer(self, project_id: int, question: str) -> QuickAnswer:
        chunks = self.repo.list_chunks(project_id)
        chunk_document_ids = {c.id: c.document_id for c in chunks}
        valid_document_ids = {c.document_id for c in chunks}
        context = build_chunk_context(chunks)
        prior_findings_context = _build_prior_findings_context(self.repo.list_findings(project_id))

        def parse(data: dict) -> QuickAnswerDraft:
            candidate = QuickAnswerDraft(**data)
            validate_evidence_citations(candidate.evidence, chunk_document_ids, valid_document_ids)
            return candidate

        draft = generate_json_with_retry(
            self.llm,
            label="QuickAnswer",
            max_retries=MAX_RETRIES,
            build_prompt=lambda error_block: PROMPT_TEMPLATE.format(
                context=context, prior_findings=prior_findings_context, question=question, error_block=error_block
            ),
            parse=parse,
        )

        findings = []
        for item in draft.evidence:
            finding = self.repo.create_finding(
                project_id=project_id,
                statement=item.statement,
                source_type=item.source_type.value,
                confidence=item.confidence.value,
                document_id=item.citation.document_id,
                chunk_id=item.citation.chunk_id,
                location=item.citation.location,
                calculation=item.calculation,
                assumption=item.assumption,
            )
            findings.append(
                FindingOut(
                    id=finding.id,
                    statement=finding.statement,
                    source_type=finding.source_type,
                    confidence=finding.confidence,
                    citation=Citation(
                        document_id=finding.document_id,
                        chunk_id=finding.chunk_id,
                        location=finding.location,
                    ),
                    calculation=finding.calculation,
                    assumption=finding.assumption,
                    origin=finding.origin,
                )
            )

        return QuickAnswer(
            answer=draft.answer,
            evidence=findings,
            reasoning=draft.reasoning,
            confidence=draft.confidence,
            missing_information=draft.missing_information,
            recommended_next_question=draft.recommended_next_question,
        )
