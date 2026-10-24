"""Spec conformance tests (Milestone B1).

Tests every single validator check with both a passing and a failing example per rule:
1. Header exactly case_id,deletion_status,steps_json
2. Row count equals request file count
3. Sorted unique case_ids (no duplicates, strictly ascending)
4. Status in the 3 allowed values (COMPLETE, INCOMPLETE, NOT_APPLICABLE)
5. steps_json parses as a JSON array
6. NOT_APPLICABLE implies []
7. Each step has exactly the 7 keys
8. step_no is consecutive 1..n
9. Every (phase, operation, state) is an allowed triple (out of 15)
10. Phase order and within-phase ordering
11. COMPLETE cases contain only VERIFICATION with valid non-empty evidence_id
12. INCOMPLETE remediation and verification steps have empty evidence_id
"""

import json
from pathlib import Path
import pytest

from backend.app.output.writer import OutputWriter, StepItem, CaseOutput
from backend.app.output.validator import OutputValidator


VALID_EVIDENCE_IDS = {"evidence_54", "evidence_01", "activity_100", "audit_200"}


def write_test_csv(path: Path, header: list, rows: list):
    """Helper to write raw CSV rows."""
    import csv
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow(r)


# --- 1. Header rule ---

def test_rule1_header_exact_match_pass(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [["case_01", "NOT_APPLICABLE", "[]"]])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1)
    assert report.passed is True


def test_rule1_header_exact_match_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "wrong_status_col", "steps_json"], [["case_01", "NOT_APPLICABLE", "[]"]])
    with pytest.raises(ValueError, match="Expected header"):
        OutputValidator.validate_or_raise(csv_file)


# --- 2. Row count rule ---

def test_rule2_row_count_pass(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", "[]"],
        ["case_02", "NOT_APPLICABLE", "[]"],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=2)
    assert report.passed is True


def test_rule2_row_count_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", "[]"],
    ])
    with pytest.raises(ValueError, match="Expected 2 rows, found 1"):
        OutputValidator.validate_or_raise(csv_file, expected_case_count=2)


# --- 3. Sorted unique case_ids ---

def test_rule3_sorted_unique_case_ids_pass(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", "[]"],
        ["case_02", "NOT_APPLICABLE", "[]"],
        ["case_03", "NOT_APPLICABLE", "[]"],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=3)
    assert report.passed is True


def test_rule3_duplicate_case_ids_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", "[]"],
        ["case_01", "NOT_APPLICABLE", "[]"],
    ])
    with pytest.raises(ValueError, match="Duplicate case_ids detected"):
        OutputValidator.validate_or_raise(csv_file)


def test_rule3_unsorted_case_ids_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_02", "NOT_APPLICABLE", "[]"],
        ["case_01", "NOT_APPLICABLE", "[]"],
    ])
    with pytest.raises(ValueError, match="not in ascending sorted order"):
        OutputValidator.validate_or_raise(csv_file)


# --- 4. Allowed statuses ---

def test_rule4_allowed_status_pass(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    step = json.dumps([{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"}])
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", step],
        ["case_02", "NOT_APPLICABLE", "[]"],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=2, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule4_disallowed_status_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "UNCERTAIN", "[]"],
    ])
    with pytest.raises(ValueError, match="invalid status 'UNCERTAIN'"):
        OutputValidator.validate_or_raise(csv_file)


# --- 5. steps_json parses as array ---

def test_rule5_steps_json_parses_array_pass(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", "[]"],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1)
    assert report.passed is True


def test_rule5_steps_json_not_array_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", '{"step_no": 1}'],
    ])
    with pytest.raises(ValueError, match="steps_json is not an array"):
        OutputValidator.validate_or_raise(csv_file)


# --- 6. NOT_APPLICABLE implies [] ---

def test_rule6_not_applicable_empty_pass(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", "[]"],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1)
    assert report.passed is True


def test_rule6_not_applicable_non_empty_fail(tmp_path: Path):
    csv_file = tmp_path / "out.csv"
    step = json.dumps([{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"}])
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "NOT_APPLICABLE", step],
    ])
    with pytest.raises(ValueError, match="NOT_APPLICABLE must have empty steps array"):
        OutputValidator.validate_or_raise(csv_file)


# --- 7. Exactly 7 keys ---

def test_rule7_exact_seven_keys_pass(tmp_path: Path):
    step = {
        "step_no": 1,
        "phase": "VERIFICATION",
        "system_id": "account_service",
        "resource_id": "account_01",
        "operation": "VERIFY_RECORD_ABSENT",
        "state": "ABSENT",
        "evidence_id": "evidence_54",
    }
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps([step])],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule7_missing_key_fail(tmp_path: Path):
    # Missing evidence_id
    bad_step = {
        "step_no": 1,
        "phase": "VERIFICATION",
        "system_id": "account_service",
        "resource_id": "account_01",
        "operation": "VERIFY_RECORD_ABSENT",
        "state": "ABSENT",
    }
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps([bad_step])],
    ])
    with pytest.raises(ValueError, match="keys mismatch"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


def test_rule7_extra_key_fail(tmp_path: Path):
    # Extra key
    bad_step = {
        "step_no": 1,
        "phase": "VERIFICATION",
        "system_id": "account_service",
        "resource_id": "account_01",
        "operation": "VERIFY_RECORD_ABSENT",
        "state": "ABSENT",
        "evidence_id": "evidence_54",
        "unexpected_field": "disallowed",
    }
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps([bad_step])],
    ])
    with pytest.raises(ValueError, match="keys mismatch"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


# --- 8. step_no consecutive 1..n ---

def test_rule8_step_no_consecutive_pass(tmp_path: Path):
    steps = [
        {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "VERIFICATION", "system_id": "search_service", "resource_id": "search_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(steps)],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule8_step_no_non_consecutive_fail(tmp_path: Path):
    steps = [
        {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
        {"step_no": 3, "phase": "VERIFICATION", "system_id": "search_service", "resource_id": "search_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(steps)],
    ])
    with pytest.raises(ValueError, match="step_no is 3, expected 2"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


# --- 9. Allowed triples (out of 15) ---

def test_rule9_allowed_triples_pass(tmp_path: Path):
    steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_01", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
        {"step_no": 3, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(steps)],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule9_disallowed_triple_fail(tmp_path: Path):
    # Invalid state for REPORT_REMAINING_RECORD (ABSENT instead of PRESENT)
    bad_steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="invalid triple"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


# --- 10. Phase and within-phase ordering ---

def test_rule10_phase_and_within_phase_order_pass(tmp_path: Path):
    # FINDING (op 0) -> REMEDIATION (op 2) -> VERIFICATION (op 0, then op 1)
    steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_01", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
        {"step_no": 3, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
        {"step_no": 4, "phase": "VERIFICATION", "system_id": "security_service", "resource_id": "audit_01", "operation": "VERIFY_RECORD_PRESENT", "state": "PRESENT", "evidence_id": ""},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(steps)],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule10_phase_order_violation_fail(tmp_path: Path):
    # REMEDIATION appears before FINDING
    bad_steps = [
        {"step_no": 1, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_01", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
        {"step_no": 2, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="ordering violation"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


def test_rule10_within_phase_operation_order_fail(tmp_path: Path):
    # In VERIFICATION, VERIFY_RECORD_PRESENT (rank 1) appears before VERIFY_RECORD_ABSENT (rank 0)
    bad_steps = [
        {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_PRESENT", "state": "PRESENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="ordering violation"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


# --- 11. COMPLETE cases citation and phase conformance ---

def test_rule11_complete_valid_citations_pass(tmp_path: Path):
    steps = [
        {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(steps)],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule11_complete_with_non_verification_phase_fail(tmp_path: Path):
    # COMPLETE case must NOT contain FINDING
    bad_steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="COMPLETE case contains non-VERIFICATION steps"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


def test_rule11_complete_with_empty_citation_fail(tmp_path: Path):
    # COMPLETE case verification must have non-empty citation
    bad_steps = [
        {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="COMPLETE case verification step has empty evidence_id"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


def test_rule11_complete_with_unknown_citation_fail(tmp_path: Path):
    # COMPLETE case verification must cite existing ID
    bad_steps = [
        {"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_UNKNOWN"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "COMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="cited evidence_id 'evidence_UNKNOWN' not found"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


# --- 12. INCOMPLETE empty citation rule ---

def test_rule12_incomplete_empty_citation_pass(tmp_path: Path):
    steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_01", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
        {"step_no": 3, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(steps)],
    ])
    report = OutputValidator.validate_or_raise(csv_file, expected_case_count=1, valid_evidence_ids=VALID_EVIDENCE_IDS)
    assert report.passed is True


def test_rule12_incomplete_remediation_has_citation_fail(tmp_path: Path):
    # INCOMPLETE remediation must have empty evidence_id
    bad_steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_01", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="INCOMPLETE REMEDIATION step must have empty evidence_id"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)


def test_rule12_incomplete_verification_has_citation_fail(tmp_path: Path):
    # INCOMPLETE verification must have empty evidence_id
    bad_steps = [
        {"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_01", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_54"},
        {"step_no": 2, "phase": "REMEDIATION", "system_id": "account_service", "resource_id": "account_01", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
        {"step_no": 3, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"},
    ]
    csv_file = tmp_path / "out.csv"
    write_test_csv(csv_file, ["case_id", "deletion_status", "steps_json"], [
        ["case_01", "INCOMPLETE", json.dumps(bad_steps)],
    ])
    with pytest.raises(ValueError, match="INCOMPLETE VERIFICATION step must have empty evidence_id"):
        OutputValidator.validate_or_raise(csv_file, valid_evidence_ids=VALID_EVIDENCE_IDS)
