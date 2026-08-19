import logging

from src.database.models import DocumentChunk
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.llm.json_utils import extract_json
from src.schemas.chat import QuickAnswer, QuickAnswerDraft
from src.schemas.evidence import Citation, FindingOut

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
MAX_CONTEXT_CHUNKS = 60  # crude context-length guard for local models; revisit with real retrieval later

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

EVIDENCE CONTEXT (each item: chunk_id, document_id, filename, location, content):
{context}

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


def _build_context(chunks: list[DocumentChunk]) -> str:
    if not chunks:
        return "(no documents have been ingested for this project yet)"

    lines = []
    for chunk in chunks[:MAX_CONTEXT_CHUNKS]:
        lines.append(
            f"- chunk_id={chunk.id} document_id={chunk.document_id} "
            f"location={chunk.location} content={chunk.content}"
        )

    return "\n".join(lines)


class QuickAnswerService:
    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def answer(self, project_id: int, question: str) -> QuickAnswer:
        chunks = self.repo.list_chunks(project_id)
        valid_chunk_ids = {c.id for c in chunks}
        valid_document_ids = {c.document_id for c in chunks}
        context = _build_context(chunks)

        last_error = ""
        draft: QuickAnswerDraft | None = None

        for attempt in range(MAX_RETRIES + 1):
            logger.info("QuickAnswer attempt %d/%d", attempt + 1, MAX_RETRIES + 1)

            prompt = PROMPT_TEMPLATE.format(
                context=context,
                question=question,
                error_block=f"PREVIOUS ATTEMPT FAILED, FIX THIS: {last_error}" if last_error else "",
            )

            raw = self.llm.generate(prompt)

            try:
                data = extract_json(raw)
                candidate = QuickAnswerDraft(**data)
                self._validate_citations(candidate, valid_chunk_ids, valid_document_ids)
                draft = candidate
                break
            except Exception as e:  # noqa: BLE001 — feed any failure back as retry context
                logger.warning("QuickAnswer parse/validation error: %s", e)
                last_error = str(e)

        if draft is None:
            raise ValueError(f"QuickAnswer failed after retries. Last error: {last_error}")

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

    @staticmethod
    def _validate_citations(
        draft: QuickAnswerDraft, valid_chunk_ids: set[int], valid_document_ids: set[int]
    ) -> None:
        for item in draft.evidence:
            chunk_id = item.citation.chunk_id
            document_id = item.citation.document_id

            if chunk_id is not None and chunk_id not in valid_chunk_ids:
                raise ValueError(f"citation.chunk_id={chunk_id} does not exist in this project's evidence context")

            if document_id is not None and document_id not in valid_document_ids:
                raise ValueError(
                    f"citation.document_id={document_id} does not exist in this project's evidence context"
                )

            if item.source_type.value == "ASSUMPTION" and chunk_id is not None:
                raise ValueError("ASSUMPTION evidence must not cite a chunk_id")
