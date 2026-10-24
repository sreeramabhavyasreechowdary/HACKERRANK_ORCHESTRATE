"""Unit tests for deterministic policy rules (Milestone B4)."""

import pytest
from backend.app.policy.rules import (
    ALLOWED_TRIPLES,
    CATEGORY_POLICY,
    StepModel,
    get_remediation_for_finding,
    get_verification_for_remediation,
    sort_steps,
)
from backend.app.state.reconstruct import CaseReconstructedState
from backend.app.policy.decide import DecisionEngine


def test_rule_primary_store_incomplete():
    """If primary DB has active data, verdict must be INCOMPLETE."""
    f = StepModel(
        step_no=1,
        phase="FINDING",
        system_id="account_service",
        resource_id="account_005",
        operation="REPORT_REMAINING_RECORD",
        state="PRESENT",
        evidence_id="evidence_54",
    )
    state = CaseReconstructedState(
        case_id="case_101",
        email="test@example.com",
        user_id="user_101",
        status="INCOMPLETE",
        findings=[f],
        final_steps=[f],
    )
    decision = DecisionEngine.decide(state)
    assert decision.deletion_status == "INCOMPLETE"
    assert "REPORT_REMAINING_RECORD" in decision.steps_json


def test_rule_complete_state():
    """If all observed resources are verified, verdict is COMPLETE."""
    v = StepModel(
        step_no=1,
        phase="VERIFICATION",
        system_id="account_service",
        resource_id="account_001",
        operation="VERIFY_RECORD_ABSENT",
        state="ABSENT",
        evidence_id="evidence_54",
    )
    state = CaseReconstructedState(
        case_id="case_102",
        email="test@example.com",
        user_id="user_102",
        status="COMPLETE",
        verifications=[v],
        final_steps=[v],
    )
    decision = DecisionEngine.decide(state)
    assert decision.deletion_status == "COMPLETE"
    assert "VERIFY_RECORD_ABSENT" in decision.steps_json


def test_rule_not_applicable_state():
    """If request is non-deletion, verdict is NOT_APPLICABLE and steps_json is []."""
    state = CaseReconstructedState(
        case_id="case_103",
        email="test@example.com",
        user_id="user_103",
        is_non_deletion=True,
        status="NOT_APPLICABLE",
        final_steps=[],
    )
    decision = DecisionEngine.decide(state)
    assert decision.deletion_status == "NOT_APPLICABLE"
    assert decision.steps_json == "[]"
