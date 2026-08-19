import logging
from typing import Callable, TypeVar

from src.llm.base import LLMClient
from src.llm.json_utils import extract_json

T = TypeVar("T")
logger = logging.getLogger(__name__)


def generate_json_with_retry(
    llm: LLMClient,
    *,
    label: str,
    max_retries: int,
    build_prompt: Callable[[str], str],
    parse: Callable[[dict], T],
) -> T:
    """Shared retry harness for every service that asks an LLM for structured
    JSON output (QuickAnswerService, BusinessUnderstandingAgent,
    HypothesisManagerAgent, ExecutiveSynthesizerService, IssueTreeService):
    format a prompt with the previous attempt's error fed back in, extract
    and parse the JSON, and retry up to `max_retries` times on any failure.

    Extracted after this exact control flow existed as 5 near-identical
    copies — the same lesson services/evidence_validation.py already applied
    once in this project: a bug fixed in one copy (the finding_id/chunk_id
    prompt conflation) stays fixed only in that one copy until the shared
    logic is factored out.

    `build_prompt(error_block)` should format the full prompt for one
    attempt, given the (possibly empty) error-feedback block to embed.
    `parse(data)` should validate `data` and raise on anything invalid
    (schema mismatch, a fabricated citation, exceeding a depth/branch limit,
    ...) — that's what triggers a retry with the error message fed back to
    the model, not just a JSON-syntax failure. Raises ValueError if every
    attempt fails.
    """
    last_error = ""

    for attempt in range(max_retries + 1):
        logger.info("%s attempt %d/%d", label, attempt + 1, max_retries + 1)

        error_block = f"PREVIOUS ATTEMPT FAILED, FIX THIS: {last_error}" if last_error else ""
        prompt = build_prompt(error_block)
        raw = llm.generate(prompt)

        try:
            data = extract_json(raw)
            return parse(data)
        except Exception as e:  # noqa: BLE001 — feed any failure back as retry context
            logger.warning("%s parse/validation error: %s", label, e)
            last_error = str(e)

    raise ValueError(f"{label} failed after retries. Last error: {last_error}")
