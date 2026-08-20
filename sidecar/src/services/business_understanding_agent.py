from src.database.models import BusinessProfile
from src.database.repository import Repository
from src.llm.base import LLMClient
from src.llm.retry import generate_json_with_retry
from src.schemas.business_profile import BusinessProfileDraft
from src.services.context_builder import build_chunk_context
from src.services.evidence_validation import validate_evidence_citations

MAX_RETRIES = 2

PROMPT_TEMPLATE = """You are a strategy-consulting-inspired business analyst. Build a business
understanding profile using ONLY the evidence provided below (spec section 3). This is Deep
Analysis mode's first step — get the fact base right before anything downstream (financial
analysis, concerns, opportunities) can be trusted.

RULES:
- Return ONLY JSON. No markdown, no prose outside the JSON.
- Every profile field is a string or null — use null (not a guess) if the evidence doesn't
  cover it. It is far better to say "not covered in the documents provided" than to infer a
  plausible-sounding business model from thin evidence.
- "evidence" must ground the profile: each item is FACT, INFERENCE, HYPOTHESIS, or ASSUMPTION
  (rarely CALCULATION — this is a qualitative profile, not arithmetic). A FACT's citation MUST
  use a real chunk_id/document_id from EVIDENCE CONTEXT below. Do NOT invent a chunk_id.
- "missing_information" lists what a complete business profile needs that the evidence doesn't
  cover (e.g. "no data on distribution channels", "no explicit customer segmentation").
- "confidence" is HIGH/MEDIUM/LOW/UNKNOWN for the profile as a whole — LOW if evidence is thin
  (e.g. a single spreadsheet with no narrative documents).

EVIDENCE CONTEXT (each item: chunk_id, document_id, filename, location, content):
{context}

{error_block}

FORMAT EXACTLY:
{{
  "business_model": "string | null",
  "products_services": "string | null",
  "customers": "string | null",
  "geographies": "string | null",
  "revenue_streams": "string | null",
  "cost_structure": "string | null",
  "value_proposition": "string | null",
  "distribution_model": "string | null",
  "competitive_position": "string | null",
  "key_capabilities": "string | null",
  "strategic_objectives": "string | null",
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
  "missing_information": ["string"],
  "confidence": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
}}
"""


class BusinessUnderstandingAgent:
    """Deep Analysis mode step 1 (spec section 2), the Business Understanding
    Agent (spec section 7). Same evidence-integrity contract as
    QuickAnswerService: real citations only, retry on invalid JSON or a
    fabricated chunk_id."""

    def __init__(self, repo: Repository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def run(self, project_id: int) -> BusinessProfile:
        chunks = self.repo.list_chunks(project_id)
        chunk_document_ids = {c.id: c.document_id for c in chunks}
        valid_document_ids = {c.document_id for c in chunks}
        context = build_chunk_context(chunks)

        def parse(data: dict) -> BusinessProfileDraft:
            candidate = BusinessProfileDraft(**data)
            validate_evidence_citations(candidate.evidence, chunk_document_ids, valid_document_ids)
            return candidate

        draft = generate_json_with_retry(
            self.llm,
            label="BusinessUnderstanding",
            max_retries=MAX_RETRIES,
            build_prompt=lambda error_block: PROMPT_TEMPLATE.format(context=context, error_block=error_block),
            parse=parse,
        )

        finding_ids = []
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
            finding_ids.append(finding.id)

        return self.repo.create_business_profile(
            project_id=project_id,
            business_model=draft.business_model,
            products_services=draft.products_services,
            customers=draft.customers,
            geographies=draft.geographies,
            revenue_streams=draft.revenue_streams,
            cost_structure=draft.cost_structure,
            value_proposition=draft.value_proposition,
            distribution_model=draft.distribution_model,
            competitive_position=draft.competitive_position,
            key_capabilities=draft.key_capabilities,
            strategic_objectives=draft.strategic_objectives,
            missing_information=draft.missing_information,
            confidence=draft.confidence.value,
            finding_ids=finding_ids,
        )
