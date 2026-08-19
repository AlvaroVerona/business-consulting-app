from src.database.models import Concern, Hypothesis, Opportunity
from src.schemas.deep_analysis import QualityIssue


class QualityReviewerService:
    """Spec section 7's Quality Reviewer: challenges unsupported conclusions,
    double counting, and weak evidence. Deliberately deterministic, not
    LLM-based — these are structural/mechanical checks (empty evidence link,
    a status the evidence doesn't support, a near-duplicate title), not
    judgment calls that need language understanding. A qualitative
    LLM-based "does this reasoning actually hold together" pass is a
    reasonable future addition, not built here."""

    def run(
        self, concerns: list[Concern], opportunities: list[Opportunity], hypotheses: list[Hypothesis]
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []

        issues.extend(self._check_unsupported(concerns, "concern"))
        issues.extend(self._check_unsupported(opportunities, "opportunity"))
        issues.extend(self._check_double_counting(concerns, "concern"))
        issues.extend(self._check_double_counting(opportunities, "opportunity"))
        issues.extend(self._check_hypothesis_status(hypotheses))

        return issues

    @staticmethod
    def _check_unsupported(entities: list, entity_type: str) -> list[QualityIssue]:
        issues = []
        for entity in entities:
            if not entity.evidence_finding_ids:
                issues.append(
                    QualityIssue(
                        entity_type=entity_type,
                        entity_id=entity.id,
                        issue="unsupported",
                        detail=f'"{entity.title}" has no evidence_finding_ids — nothing grounds this claim.',
                    )
                )
        return issues

    @staticmethod
    def _check_double_counting(entities: list, entity_type: str) -> list[QualityIssue]:
        issues = []
        seen: dict[str, object] = {}
        # Repository list_* methods return newest-first; sort ascending by id
        # (creation order — more reliable than created_at, whose resolution
        # can tie for two rows inserted in the same test/request) so the
        # entity created *later* is always the one flagged as the duplicate.
        for entity in sorted(entities, key=lambda e: e.id):
            key = entity.title.strip().lower()
            if key in seen:
                issues.append(
                    QualityIssue(
                        entity_type=entity_type,
                        entity_id=entity.id,
                        issue="possible double counting",
                        detail=f'"{entity.title}" duplicates {entity_type} #{seen[key]} — likely the same underlying issue detected twice.',
                    )
                )
            else:
                seen[key] = entity.id
        return issues

    @staticmethod
    def _check_hypothesis_status(hypotheses: list[Hypothesis]) -> list[QualityIssue]:
        issues = []
        for h in hypotheses:
            if h.status in ("CONFIRMED", "STRONGLY_SUPPORTED") and not h.supporting_finding_ids:
                issues.append(
                    QualityIssue(
                        entity_type="hypothesis",
                        entity_id=h.id,
                        issue="status not evidenced",
                        detail=f'Hypothesis "{h.statement}" is marked {h.status} but has no supporting_finding_ids.',
                    )
                )
            if h.status == "CONTRADICTED" and not h.contradicting_finding_ids:
                issues.append(
                    QualityIssue(
                        entity_type="hypothesis",
                        entity_id=h.id,
                        issue="status not evidenced",
                        detail=f'Hypothesis "{h.statement}" is marked CONTRADICTED but has no contradicting_finding_ids.',
                    )
                )
        return issues
