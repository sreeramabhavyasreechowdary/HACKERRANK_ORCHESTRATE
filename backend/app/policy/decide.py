"""Decision Engine Producing Schema-Exact Verified Verdicts (Milestone B4).

Applies deterministic rules and builds conforming output rows.
"""

import json
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from backend.app.policy.rules import StepModel
from backend.app.state.reconstruct import CaseReconstructedState


class OutputRow(BaseModel):
    """A single conforming row for output.csv."""
    case_id: str
    deletion_status: str
    steps_json: str

    def to_csv_dict(self) -> Dict[str, str]:
        return {
            "case_id": self.case_id,
            "deletion_status": self.deletion_status,
            "steps_json": self.steps_json,
        }


class DecisionEngine:
    """Produces the final schema-exact verdict and step JSON for a case."""

    @classmethod
    def decide(cls, state: CaseReconstructedState) -> OutputRow:
        """Construct the final verified OutputRow."""
        if state.is_non_deletion or state.status == "NOT_APPLICABLE":
            return OutputRow(
                case_id=state.case_id,
                deletion_status="NOT_APPLICABLE",
                steps_json="[]",
            )

        # Build steps array
        steps_dicts = [s.to_dict() for s in state.final_steps]
        steps_json = json.dumps(steps_dicts, separators=(",", ":"))

        return OutputRow(
            case_id=state.case_id,
            deletion_status=state.status,
            steps_json=steps_json,
        )
