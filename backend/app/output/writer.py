"""Output CSV Writer (FR-17, Hard Rule 5, Milestone B1).

Writes output.csv strictly using python's csv module or pandas, never string concatenation.
Ensures exact columns: case_id,deletion_status,steps_json.
Ensures ascending sort by case_id.
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Union
import pandas as pd
from pydantic import BaseModel, Field


class StepItem(BaseModel):
    """Exactly the 7 keys required per step."""
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str = ""


class CaseOutput(BaseModel):
    """A single row in output.csv."""
    case_id: str
    deletion_status: str
    steps_json: Union[List[Dict[str, Any]], List[StepItem], str]


class OutputWriter:
    """Writes case decisions to output.csv adhering strictly to schema and quoting rules."""

    COLUMNS = ["case_id", "deletion_status", "steps_json"]

    @classmethod
    def write(cls, rows: List[Union[CaseOutput, Dict[str, Any]]], output_path: Path) -> Path:
        """
        Write rows to output.csv with ascending case_id order.
        Guarantees exact header: case_id,deletion_status,steps_json.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Normalize and sort by ascending case_id
        normalized = []
        for r in rows:
            if isinstance(r, CaseOutput):
                cid = r.case_id
                status = r.deletion_status
                steps = r.steps_json
            else:
                cid = str(r["case_id"])
                status = str(r["deletion_status"])
                steps = r.get("steps_json", [])

            # Format steps_json
            if status == "NOT_APPLICABLE":
                formatted_steps_json = "[]"
            elif isinstance(steps, str):
                # Ensure it's valid JSON
                parsed = json.loads(steps)
                formatted_steps_json = json.dumps(parsed)
            elif isinstance(steps, list):
                # If list of StepItem, dump to dict
                steps_data = [s.model_dump() if hasattr(s, "model_dump") else s for s in steps]
                formatted_steps_json = json.dumps(steps_data)
            else:
                formatted_steps_json = json.dumps(steps)

            normalized.append({
                "case_id": cid,
                "deletion_status": status,
                "steps_json": formatted_steps_json,
            })

        # Ascending sort key
        def sort_key(item):
            cid = item["case_id"]
            # Handle case_01, case_001, etc.
            if cid.startswith("case_"):
                suffix = cid[5:]
                if suffix.isdigit():
                    return (0, int(suffix), cid)
            if cid.isdigit():
                return (0, int(cid), cid)
            return (1, 0, str(cid))

        sorted_rows = sorted(normalized, key=sort_key)

        # Write using pandas / csv module
        df = pd.DataFrame(sorted_rows, columns=cls.COLUMNS)
        df.to_csv(output_path, index=False, quoting=csv.QUOTE_MINIMAL, encoding="utf-8")

        return output_path
