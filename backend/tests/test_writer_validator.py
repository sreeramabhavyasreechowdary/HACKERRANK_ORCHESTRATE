"""Unit tests for OutputWriter and OutputValidator roundtrip (Milestone B1)."""

import json
from pathlib import Path
import pytest
from backend.app.output.writer import OutputWriter, StepItem, CaseOutput
from backend.app.output.validator import OutputValidator


def test_writer_and_validator_roundtrip(tmp_path: Path):
    """Verify generated output.csv strictly passes the validator."""
    output_file = tmp_path / "output.csv"

    rows = [
        CaseOutput(
            case_id="case_002",
            deletion_status="NOT_APPLICABLE",
            steps_json=[],
        ),
        CaseOutput(
            case_id="case_001",
            deletion_status="COMPLETE",
            steps_json=[
                StepItem(
                    step_no=1,
                    phase="VERIFICATION",
                    system_id="account_service",
                    resource_id="account_001",
                    operation="VERIFY_RECORD_ABSENT",
                    state="ABSENT",
                    evidence_id="evidence_54",
                )
            ],
        ),
    ]

    # Writer must sort ascending by case_id
    OutputWriter.write(rows, output_file)

    # Validate
    report = OutputValidator.validate_or_raise(
        output_path=output_file,
        expected_case_count=2,
        valid_evidence_ids={"evidence_54"},
    )
    assert report.passed is True

    # Re-read raw content to verify sort order (case_001 must appear before case_002)
    with open(output_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert "case_001" in lines[1]
        assert "case_002" in lines[2]
