"""Failure Analysis and Tagging (FR-21).

Tags prediction errors into structured failure categories:
- MISREAD_EVIDENCE
- MISSED_LOCATION
- WRONG_POLICY_APPLIED
- CONFLICT_MISHANDLED
- EXTRACTION_FAILURE
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from backend.app.policy.decide import CaseDecision
from backend.app.state.reconstruct import CaseReconstructedState, LocationStatus


class FailureItem(BaseModel):
    case_id: str
    true_verdict: str
    predicted_verdict: str
    category: str
    reason: str


class FailureReport(BaseModel):
    total_failures: int
    grouped_by_category: Dict[str, List[str]] = Field(default_factory=dict)
    failures: List[FailureItem] = Field(default_factory=list)


class FailureAnalyzer:
    """Analyzes differences between true verdicts and predictions."""

    @classmethod
    def analyze_case(
        cls,
        case_id: str,
        true_verdict: str,
        predicted_verdict: str,
        decision: CaseDecision,
        state: Optional[CaseReconstructedState] = None,
    ) -> Optional[FailureItem]:
        """Classify why a case prediction failed."""
        if true_verdict == predicted_verdict:
            return None

        category = "WRONG_POLICY_APPLIED"

        if state:
            if state.has_any_conflict:
                category = "CONFLICT_MISHANDLED"
            elif any(s.status == LocationStatus.UNKNOWN for s in state.locations.values()):
                category = "MISSED_LOCATION"
            elif not decision.citations:
                category = "EXTRACTION_FAILURE"
            else:
                category = "MISREAD_EVIDENCE"

        return FailureItem(
            case_id=case_id,
            true_verdict=true_verdict,
            predicted_verdict=predicted_verdict,
            category=category,
            reason=f"Predicted '{predicted_verdict}' but truth was '{true_verdict}'. Triggered rules: {decision.rules_fired}",
        )

    @classmethod
    def build_report(cls, failure_items: List[FailureItem]) -> FailureReport:
        """Group failures by category."""
        grouped: Dict[str, List[str]] = {}
        for item in failure_items:
            grouped.setdefault(item.category, []).append(item.case_id)

        return FailureReport(
            total_failures=len(failure_items),
            grouped_by_category=grouped,
            failures=failure_items,
        )
