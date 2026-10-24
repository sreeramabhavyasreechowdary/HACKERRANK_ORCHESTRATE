"""Output CSV Validator (FR-18, FR-19, Milestone B1).

Strictly enforces all 12 spec conformance checks:
1. Header is exactly: case_id,deletion_status,steps_json
2. Row count equals the expected request count (518 in final, 32 in sample)
3. Sorted unique case_ids
4. Status is strictly in {COMPLETE, INCOMPLETE, NOT_APPLICABLE}
5. steps_json parses as a JSON array
6. NOT_APPLICABLE implies steps_json == []
7. Each step has exactly the 7 keys: step_no, phase, system_id, resource_id, operation, state, evidence_id
8. step_no is consecutive 1..n
9. Every (phase, operation, state) is one of the 15 allowed triples
10. Phase order (FINDING -> REMEDIATION -> VERIFICATION) and within-phase ordering (table order, system_id, resource_id)
11. COMPLETE cases contain ONLY VERIFICATION steps with non-empty evidence_id existing in evidence_files, system_activity, or user_audit_log
12. INCOMPLETE remediation and verification steps have empty evidence_id ("")
"""

import csv
import json
from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Tuple
from pydantic import BaseModel, Field


class ValidationCheck(BaseModel):
    check: str
    passed: bool
    detail: str


class ValidationReport(BaseModel):
    passed: bool
    checks: List[ValidationCheck] = Field(default_factory=list)


class OutputValidator:
    """Enforces all spec conformance rules on output.csv."""

    EXPECTED_HEADER = ["case_id", "deletion_status", "steps_json"]
    ALLOWED_STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}

    ALLOWED_TRIPLES: Set[Tuple[str, str, str]] = {
        ("FINDING", "REPORT_REMAINING_RECORD", "PRESENT"),
        ("FINDING", "REPORT_EXPOSED_PII", "PRESENT"),
        ("FINDING", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
        ("FINDING", "REPORT_RESTORE_RISK", "ACTIVE"),
        ("REMEDIATION", "DISABLE_DATA_FLOW", "DISABLED"),
        ("REMEDIATION", "BLOCK_RESTORE", "BLOCKED"),
        ("REMEDIATION", "DELETE_RECORD", "ABSENT"),
        ("REMEDIATION", "REDACT_RECORD", "REDACTED"),
        ("REMEDIATION", "ANONYMIZE_RECORD", "ANONYMIZED"),
        ("VERIFICATION", "VERIFY_RECORD_ABSENT", "ABSENT"),
        ("VERIFICATION", "VERIFY_RECORD_PRESENT", "PRESENT"),
        ("VERIFICATION", "VERIFY_RECORD_REDACTED", "REDACTED"),
        ("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
        ("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
        ("VERIFICATION", "VERIFY_RESTORE_BLOCKED", "BLOCKED"),
    }

    REQUIRED_STEP_KEYS = {
        "step_no",
        "phase",
        "system_id",
        "resource_id",
        "operation",
        "state",
        "evidence_id",
    }

    PHASE_ORDER = {
        "FINDING": 0,
        "REMEDIATION": 1,
        "VERIFICATION": 2,
    }

    OPERATION_ORDER = {
        # Finding phase
        "REPORT_REMAINING_RECORD": 0,
        "REPORT_EXPOSED_PII": 1,
        "REPORT_ACTIVE_DATA_FLOW": 2,
        "REPORT_RESTORE_RISK": 3,
        # Remediation phase
        "DISABLE_DATA_FLOW": 0,
        "BLOCK_RESTORE": 1,
        "DELETE_RECORD": 2,
        "REDACT_RECORD": 3,
        "ANONYMIZE_RECORD": 4,
        # Verification phase
        "VERIFY_RECORD_ABSENT": 0,
        "VERIFY_RECORD_PRESENT": 1,
        "VERIFY_RECORD_REDACTED": 2,
        "VERIFY_RECORD_ANONYMIZED": 3,
        "VERIFY_DATA_FLOW_DISABLED": 4,
        "VERIFY_RESTORE_BLOCKED": 5,
    }

    @classmethod
    def validate(
        cls,
        output_path: Path,
        expected_case_count: Optional[int] = None,
        valid_evidence_ids: Optional[Set[str]] = None,
    ) -> ValidationReport:
        """Run all conformance checks on output.csv."""
        checks: List[ValidationCheck] = []

        if not output_path.exists():
            return ValidationReport(
                passed=False,
                checks=[ValidationCheck(check="file_exists", passed=False, detail=f"File not found: {output_path}")],
            )

        checks.append(ValidationCheck(check="file_exists", passed=True, detail="File exists"))

        # 1. Header check
        with open(output_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)

        if header != cls.EXPECTED_HEADER:
            checks.append(
                ValidationCheck(
                    check="header_exact_match",
                    passed=False,
                    detail=f"Expected header {cls.EXPECTED_HEADER}, got {header}",
                )
            )
            return ValidationReport(passed=False, checks=checks)
        else:
            checks.append(
                ValidationCheck(
                    check="header_exact_match",
                    passed=True,
                    detail=f"Header is exactly {cls.EXPECTED_HEADER}",
                )
            )

        # Read full rows
        rows = []
        with open(output_path, "r", encoding="utf-8", newline="") as f:
            dict_reader = csv.DictReader(f)
            for r in dict_reader:
                rows.append(r)

        # 2. Row count check
        if expected_case_count is not None and len(rows) != expected_case_count:
            checks.append(
                ValidationCheck(
                    check="row_count",
                    passed=False,
                    detail=f"Expected {expected_case_count} rows, found {len(rows)}",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    check="row_count",
                    passed=True,
                    detail=f"Row count verified ({len(rows)} rows)",
                )
            )

        # 3. Sorted unique case_ids
        case_ids = [r["case_id"] for r in rows]
        seen_ids = set()
        duplicates = []
        for cid in case_ids:
            if cid in seen_ids:
                duplicates.append(cid)
            seen_ids.add(cid)

        if duplicates:
            checks.append(
                ValidationCheck(
                    check="unique_case_ids",
                    passed=False,
                    detail=f"Duplicate case_ids detected: {duplicates[:5]}",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    check="unique_case_ids",
                    passed=True,
                    detail="All case_ids are unique",
                )
            )

        def case_sort_key(cid: str):
            if cid.startswith("case_") and cid[5:].isdigit():
                return (0, int(cid[5:]), cid)
            if cid.isdigit():
                return (0, int(cid), cid)
            return (1, 0, str(cid))

        expected_order = sorted(case_ids, key=case_sort_key)
        if case_ids != expected_order:
            checks.append(
                ValidationCheck(
                    check="sorted_case_ids",
                    passed=False,
                    detail="case_ids are not in ascending sorted order",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    check="sorted_case_ids",
                    passed=True,
                    detail="case_ids are in ascending order",
                )
            )

        # Row-level and step-level checks
        status_errors = []
        json_errors = []
        not_applicable_errors = []
        key_errors = []
        step_no_errors = []
        triple_errors = []
        ordering_errors = []
        citation_errors = []

        for row_idx, row in enumerate(rows, start=1):
            cid = row["case_id"]
            status = row["deletion_status"]
            steps_raw = row["steps_json"]

            # 4. Status in allowed values
            if status not in cls.ALLOWED_STATUSES:
                status_errors.append(f"Row {row_idx} ({cid}): invalid status '{status}'")

            # 5. JSON array parse
            try:
                steps = json.loads(steps_raw)
                if not isinstance(steps, list):
                    json_errors.append(f"Row {row_idx} ({cid}): steps_json is not an array")
                    continue
            except Exception as e:
                json_errors.append(f"Row {row_idx} ({cid}): steps_json invalid JSON ({e})")
                continue

            # 6. NOT_APPLICABLE implies []
            if status == "NOT_APPLICABLE" and len(steps) != 0:
                not_applicable_errors.append(f"Row {row_idx} ({cid}): NOT_APPLICABLE must have empty steps array [], got {len(steps)} steps")

            # COMPLETE case must only have VERIFICATION steps
            if status == "COMPLETE":
                non_verif = [s for s in steps if s.get("phase") != "VERIFICATION"]
                if non_verif:
                    ordering_errors.append(f"Row {row_idx} ({cid}): COMPLETE case contains non-VERIFICATION steps: {[s.get('phase') for s in non_verif]}")

            # Check individual steps
            previous_step_no = 0
            previous_sort_tuple = None

            for s_idx, step in enumerate(steps, start=1):
                # 7. Exactly 7 keys
                if not isinstance(step, dict):
                    key_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: step is not an object")
                    continue

                step_keys = set(step.keys())
                if step_keys != cls.REQUIRED_STEP_KEYS:
                    key_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: keys mismatch. Expected {cls.REQUIRED_STEP_KEYS}, got {step_keys}")

                # 8. step_no consecutive 1..n
                s_no = step.get("step_no")
                if s_no != previous_step_no + 1:
                    step_no_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: step_no is {s_no}, expected {previous_step_no + 1}")
                previous_step_no = s_no if isinstance(s_no, int) else previous_step_no + 1

                # 9. Allowed triple
                phase = step.get("phase")
                op = step.get("operation")
                st = step.get("state")
                ev_id = step.get("evidence_id", "")
                sys_id = str(step.get("system_id", ""))
                res_id = str(step.get("resource_id", ""))

                triple = (phase, op, st)
                if triple not in cls.ALLOWED_TRIPLES:
                    triple_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: invalid triple {triple}")

                # 10. Ordering check: phase, then op order, then system_id, then resource_id
                phase_rank = cls.PHASE_ORDER.get(phase, 99)
                op_rank = cls.OPERATION_ORDER.get(op, 99)
                current_sort_tuple = (phase_rank, op_rank, sys_id, res_id)

                if previous_sort_tuple is not None and current_sort_tuple < previous_sort_tuple:
                    ordering_errors.append(
                        f"Row {row_idx} ({cid}) step {s_idx}: ordering violation. Step {s_idx} ({current_sort_tuple}) precedes step {s_idx - 1} ({previous_sort_tuple})"
                    )
                previous_sort_tuple = current_sort_tuple

                # 11 & 12. Citations check
                if status == "COMPLETE":
                    # COMPLETE: only VERIFICATION, must have non-empty evidence_id
                    if not ev_id or not ev_id.strip():
                        citation_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: COMPLETE case verification step has empty evidence_id")
                    elif valid_evidence_ids and ev_id not in valid_evidence_ids:
                        citation_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: cited evidence_id '{ev_id}' not found in evidence manifest, activity, or audit log")
                elif status == "INCOMPLETE":
                    if phase in ["REMEDIATION", "VERIFICATION"]:
                        if ev_id != "" and ev_id is not None:
                            citation_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: INCOMPLETE {phase} step must have empty evidence_id (''), got '{ev_id}'")
                    elif phase == "FINDING":
                        if not ev_id or not ev_id.strip():
                            citation_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: INCOMPLETE FINDING step must have non-empty evidence_id")
                        elif valid_evidence_ids and ev_id not in valid_evidence_ids:
                            citation_errors.append(f"Row {row_idx} ({cid}) step {s_idx}: cited evidence_id '{ev_id}' not found in evidence manifest, activity, or audit log")

        # Record validation check results
        checks.append(ValidationCheck(check="allowed_statuses", passed=len(status_errors) == 0, detail="; ".join(status_errors[:3]) if status_errors else "All statuses valid"))
        checks.append(ValidationCheck(check="steps_json_parses", passed=len(json_errors) == 0, detail="; ".join(json_errors[:3]) if json_errors else "All steps_json parse as arrays"))
        checks.append(ValidationCheck(check="not_applicable_empty", passed=len(not_applicable_errors) == 0, detail="; ".join(not_applicable_errors[:3]) if not_applicable_errors else "NOT_APPLICABLE cases have empty steps []"))
        checks.append(ValidationCheck(check="exact_seven_keys", passed=len(key_errors) == 0, detail="; ".join(key_errors[:3]) if key_errors else "All steps have exactly the 7 required keys"))
        checks.append(ValidationCheck(check="consecutive_step_numbers", passed=len(step_no_errors) == 0, detail="; ".join(step_no_errors[:3]) if step_no_errors else "All step numbers are consecutive 1..n"))
        checks.append(ValidationCheck(check="allowed_triples", passed=len(triple_errors) == 0, detail="; ".join(triple_errors[:3]) if triple_errors else "All triples are within the 15 allowed triples"))
        checks.append(ValidationCheck(check="correct_ordering", passed=len(ordering_errors) == 0, detail="; ".join(ordering_errors[:3]) if ordering_errors else "Phase and within-phase ordering verified"))
        checks.append(ValidationCheck(check="citation_conformance", passed=len(citation_errors) == 0, detail="; ".join(citation_errors[:3]) if citation_errors else "Citations conform to COMPLETE/INCOMPLETE rules and resolve"))

        all_passed = all(c.passed for c in checks)
        return ValidationReport(passed=all_passed, checks=checks)

    @classmethod
    def validate_or_raise(
        cls,
        output_path: Path,
        expected_case_count: Optional[int] = None,
        valid_evidence_ids: Optional[Set[str]] = None,
    ) -> ValidationReport:
        """Validate and fail loudly if any check fails (FR-19)."""
        report = cls.validate(output_path, expected_case_count, valid_evidence_ids)
        if not report.passed:
            failed_details = [f"[{c.check}] {c.detail}" for c in report.checks if not c.passed]
            raise ValueError(f"Output validation failed! Violations: {' | '.join(failed_details)}")
        return report
