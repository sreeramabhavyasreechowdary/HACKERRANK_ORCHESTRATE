"""Unit Tests for Milestone B4: Identity, State, and Deletion Rules.

Tests:
1. Identity resolution across current and historical identifiers.
2. Category-to-action policy rules (DELETE, REDACT, ANONYMIZE, RETAIN).
3. Tombstone handling (preserves stable user_id, redacts direct PII).
4. Active data flow detection (DISABLE_DATA_FLOW, VERIFY_DATA_FLOW_DISABLED).
5. Restore risk detection (BLOCK_RESTORE, VERIFY_RESTORE_BLOCKED).
6. Non-deletion request classification (NOT_APPLICABLE with empty steps []).
7. Strict 15 allowed triples and phase/operation ordering.
"""

import pytest
import pandas as pd
from backend.app.ingest.identity import IdentityResolver, ResolvedIdentity
from backend.app.ingest.loader import DeletionRequest
from backend.app.policy.rules import (
    ALLOWED_TRIPLES,
    CATEGORY_POLICY,
    StepModel,
    get_remediation_for_finding,
    get_verification_for_remediation,
    sort_steps,
)
from backend.app.state.reconstruct import StateReconstructor, CaseReconstructedState
from backend.app.policy.decide import DecisionEngine
from backend.app.extract.evidence_repo import EvidenceRepository, EvidenceObservation


@pytest.fixture
def sample_identity_resolver():
    identities_df = pd.DataFrame([
        {
            "user_id": "user_100",
            "name": "Alice Smith",
            "email": "alice.new@example.com",
            "phone": "+1-555-0100",
            "email_hash": "hash_alice_new",
            "updated_at": "2026-08-01T12:00:00Z",
        }
    ])
    audit_log_df = pd.DataFrame([
        {
            "audit_id": "audit_01",
            "user_id": "user_100",
            "event_time": "2026-07-01T12:00:00Z",
            "field_name": "email",
            "old_value": "alice.old@example.com",
            "new_value": "alice.new@example.com",
        },
        {
            "audit_id": "audit_02",
            "user_id": "user_100",
            "event_time": "2026-07-01T12:00:00Z",
            "field_name": "email_hash",
            "old_value": "hash_alice_old",
            "new_value": "hash_alice_new",
        },
        {
            "audit_id": "audit_03",
            "user_id": "user_100",
            "event_time": "2026-07-01T12:00:00Z",
            "field_name": "phone",
            "old_value": "+1-555-0099",
            "new_value": "+1-555-0100",
        },
    ])
    return IdentityResolver(identities_df, audit_log_df)


def test_identity_resolution_current_and_historical(sample_identity_resolver):
    # Lookup by old email
    ident = sample_identity_resolver.resolve("alice.old@example.com")
    assert ident is not None
    assert ident.user_id == "user_100"
    assert "alice.new@example.com" in ident.emails
    assert "alice.old@example.com" in ident.emails
    assert "hash_alice_old" in ident.email_hashes
    assert "hash_alice_new" in ident.email_hashes
    assert "+1-555-0099" in ident.phones
    assert "+1-555-0100" in ident.phones


def test_allowed_triples_completeness():
    assert len(ALLOWED_TRIPLES) == 15
    for phase, op, state in ALLOWED_TRIPLES:
        assert phase in ["FINDING", "REMEDIATION", "VERIFICATION"]
        assert state in ["PRESENT", "ABSENT", "ACTIVE", "DISABLED", "BLOCKED", "REDACTED", "ANONYMIZED"]


def test_policy_category_mappings():
    assert CATEGORY_POLICY["USER_PROFILE"] == "DELETE"
    assert CATEGORY_POLICY["SEARCH_INDEX_ENTRY"] == "DELETE"
    assert CATEGORY_POLICY["SUPPORT_MESSAGE"] == "REDACT"
    assert CATEGORY_POLICY["ANALYTICS_PROFILE"] == "ANONYMIZE"
    assert CATEGORY_POLICY["SECURITY_AUDIT_LOG"] == "RETAIN"
    assert CATEGORY_POLICY["ACCOUNT_TOMBSTONE"] == "REDACT"
    assert CATEGORY_POLICY["DATA_FLOW"] == "DISABLE"


def test_tombstone_pii_remediation():
    rem_op, rem_state = get_remediation_for_finding(
        system_id="identity_service",
        resource_id="tombstone_001",
        operation="REPORT_EXPOSED_PII",
        category="ACCOUNT_TOMBSTONE",
    )
    assert rem_op == "REDACT_RECORD"
    assert rem_state == "REDACTED"
    assert ("REMEDIATION", rem_op, rem_state) in ALLOWED_TRIPLES

    v_op, v_state = get_verification_for_remediation(rem_op)
    assert v_op == "VERIFY_RECORD_REDACTED"
    assert v_state == "REDACTED"
    assert ("VERIFICATION", v_op, v_state) in ALLOWED_TRIPLES


def test_active_data_flow_remediation():
    rem_op, rem_state = get_remediation_for_finding(
        system_id="integration_service",
        resource_id="data_flow_001",
        operation="REPORT_ACTIVE_DATA_FLOW",
        category="DATA_FLOW",
    )
    assert rem_op == "DISABLE_DATA_FLOW"
    assert rem_state == "DISABLED"
    assert ("REMEDIATION", rem_op, rem_state) in ALLOWED_TRIPLES

    v_op, v_state = get_verification_for_remediation(rem_op)
    assert v_op == "VERIFY_DATA_FLOW_DISABLED"
    assert v_state == "DISABLED"
    assert ("VERIFICATION", v_op, v_state) in ALLOWED_TRIPLES


def test_restore_risk_remediation():
    rem_op, rem_state = get_remediation_for_finding(
        system_id="backup_service",
        resource_id="backup_001",
        operation="REPORT_RESTORE_RISK",
        category="BACKUP_ARCHIVE",
    )
    assert rem_op == "BLOCK_RESTORE"
    assert rem_state == "BLOCKED"
    assert ("REMEDIATION", rem_op, rem_state) in ALLOWED_TRIPLES

    v_op, v_state = get_verification_for_remediation(rem_op)
    assert v_op == "VERIFY_RESTORE_BLOCKED"
    assert v_state == "BLOCKED"
    assert ("VERIFICATION", v_op, v_state) in ALLOWED_TRIPLES


def test_step_ordering_rule():
    unordered = [
        StepModel(step_no=0, phase="VERIFICATION", system_id="search_service", resource_id="search_002", operation="VERIFY_RECORD_ABSENT", state="ABSENT", evidence_id=""),
        StepModel(step_no=0, phase="FINDING", system_id="account_service", resource_id="account_001", operation="REPORT_REMAINING_RECORD", state="PRESENT", evidence_id="ev_01"),
        StepModel(step_no=0, phase="VERIFICATION", system_id="account_service", resource_id="account_001", operation="VERIFY_RECORD_ABSENT", state="ABSENT", evidence_id=""),
        StepModel(step_no=0, phase="REMEDIATION", system_id="account_service", resource_id="account_001", operation="DELETE_RECORD", state="ABSENT", evidence_id=""),
    ]
    ordered = sort_steps(unordered)
    assert [s.step_no for s in ordered] == [1, 2, 3, 4]
    assert ordered[0].phase == "FINDING"
    assert ordered[1].phase == "REMEDIATION"
    assert ordered[2].phase == "VERIFICATION"
    assert ordered[2].system_id == "account_service"
    assert ordered[3].phase == "VERIFICATION"
    assert ordered[3].system_id == "search_service"


def test_non_deletion_decision():
    req = DeletionRequest(
        case_id="case_non_del",
        email="user.inquiry@example.com",
        requested_at="2026-09-01T12:00:00Z",
        reported_status="NOT_STARTED",
        reported_at="2026-09-02T12:00:00Z",
        audit_at="2026-09-10T12:00:00Z",
        request_text="Can you tell me what personal information you hold about me? This is an information request, not a request to erase it.",
    )
    ident = ResolvedIdentity(
        user_id="user_non_del",
        primary_email="user.inquiry@example.com",
        emails={"user.inquiry@example.com"},
        all_terms={"user.inquiry@example.com", "user_non_del"},
    )
    empty_manifest = pd.DataFrame(columns=["file_id", "file_path", "origin", "captured_at"])
    repo = EvidenceRepository(empty_manifest)
    sys_act = pd.DataFrame(columns=["activity_id", "event_time", "event_type", "source_system", "target_system", "resource_id", "reported_result", "details"])
    reconstructor = StateReconstructor(repo, sys_act)
    state = reconstructor.reconstruct_case(req, ident)
    assert state.is_non_deletion is True
    assert state.status == "NOT_APPLICABLE"

    decision = DecisionEngine.decide(state)
    assert decision.deletion_status == "NOT_APPLICABLE"
    assert decision.steps_json == "[]"
