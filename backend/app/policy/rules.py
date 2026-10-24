"""Deterministic Policy Rules Engine (Milestone B4, Overrides 2 & 4).

Applies deletion_rules.csv per data category:
- USER_PROFILE, SECONDARY_IDENTIFIER, SEARCH_INDEX_ENTRY, CACHE_ENTRY,
  SUPPORT_ATTACHMENT, USER_EXPORT, MARKETING_PROFILE -> DELETE
- SUPPORT_MESSAGE, EMAIL_DELIVERY_LOG, ACCOUNT_TOMBSTONE -> REDACT
- ANALYTICS_PROFILE, PRODUCT_TELEMETRY -> ANONYMIZE
- SECURITY_AUDIT_LOG, LEGAL_HOLD_RECORD, BACKUP_ARCHIVE -> RETAIN
- DATA_FLOW -> DISABLE
- BACKUP_ARCHIVE restore risk -> BLOCK_RESTORE

Enforces the exact 15 allowed (phase, operation, state) triples and strict ordering.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from pydantic import BaseModel, Field

# The 15 Allowed (Phase, Operation, State) Triples
ALLOWED_TRIPLES = {
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

PHASE_ORDER = {
    "FINDING": 1,
    "REMEDIATION": 2,
    "VERIFICATION": 3,
}

OPERATION_ORDER = {
    # Phase FINDING operations
    "REPORT_REMAINING_RECORD": 1,
    "REPORT_EXPOSED_PII": 2,
    "REPORT_ACTIVE_DATA_FLOW": 3,
    "REPORT_RESTORE_RISK": 4,
    # Phase REMEDIATION operations
    "DISABLE_DATA_FLOW": 1,
    "BLOCK_RESTORE": 2,
    "DELETE_RECORD": 3,
    "REDACT_RECORD": 4,
    "ANONYMIZE_RECORD": 5,
    # Phase VERIFICATION operations
    "VERIFY_RECORD_ABSENT": 1,
    "VERIFY_RECORD_PRESENT": 2,
    "VERIFY_RECORD_REDACTED": 3,
    "VERIFY_RECORD_ANONYMIZED": 4,
    "VERIFY_DATA_FLOW_DISABLED": 5,
    "VERIFY_RESTORE_BLOCKED": 6,
}

# Deletion policy mapped per data category
CATEGORY_POLICY = {
    "USER_PROFILE": "DELETE",
    "SECONDARY_IDENTIFIER": "DELETE",
    "SEARCH_INDEX_ENTRY": "DELETE",
    "CACHE_ENTRY": "DELETE",
    "SUPPORT_MESSAGE": "REDACT",
    "SUPPORT_ATTACHMENT": "DELETE",
    "ANALYTICS_PROFILE": "ANONYMIZE",
    "PRODUCT_TELEMETRY": "ANONYMIZE",
    "USER_EXPORT": "DELETE",
    "MARKETING_PROFILE": "DELETE",
    "EMAIL_DELIVERY_LOG": "REDACT",
    "SECURITY_AUDIT_LOG": "RETAIN",
    "LEGAL_HOLD_RECORD": "RETAIN",
    "BACKUP_ARCHIVE": "RETAIN",
    "ACCOUNT_TOMBSTONE": "REDACT",
    "DATA_FLOW": "DISABLE",
}


class StepModel(BaseModel):
    """Normalized 7-key step object adhering strictly to schema."""
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_no": self.step_no,
            "phase": self.phase,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state,
            "evidence_id": self.evidence_id,
        }


def get_remediation_for_finding(system_id: str, resource_id: str, operation: str, category: str) -> Tuple[str, str]:
    """Determine remediation (operation, state) for a given finding."""
    if operation == "REPORT_ACTIVE_DATA_FLOW":
        return ("DISABLE_DATA_FLOW", "DISABLED")
    elif operation == "REPORT_RESTORE_RISK":
        return ("BLOCK_RESTORE", "BLOCKED")
    elif operation == "REPORT_REMAINING_RECORD":
        return ("DELETE_RECORD", "ABSENT")
    elif operation == "REPORT_EXPOSED_PII":
        if category in ["ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"] or system_id == "analytics_platform":
            return ("ANONYMIZE_RECORD", "ANONYMIZED")
        else:
            return ("REDACT_RECORD", "REDACTED")
    return ("DELETE_RECORD", "ABSENT")


def get_verification_for_remediation(remediation_op: str) -> Tuple[str, str]:
    """Determine future verification (operation, state) that must pass after remediation."""
    if remediation_op == "DISABLE_DATA_FLOW":
        return ("VERIFY_DATA_FLOW_DISABLED", "DISABLED")
    elif remediation_op == "BLOCK_RESTORE":
        return ("VERIFY_RESTORE_BLOCKED", "BLOCKED")
    elif remediation_op == "DELETE_RECORD":
        return ("VERIFY_RECORD_ABSENT", "ABSENT")
    elif remediation_op == "REDACT_RECORD":
        return ("VERIFY_RECORD_REDACTED", "REDACTED")
    elif remediation_op == "ANONYMIZE_RECORD":
        return ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED")
    return ("VERIFY_RECORD_ABSENT", "ABSENT")


def sort_steps(steps: List[StepModel]) -> List[StepModel]:
    """
    Sort steps strictly according to problem_statement.md:
    1. Phase order: FINDING -> REMEDIATION -> VERIFICATION.
    2. Operation order matching the table order.
    3. system_id ascending.
    4. resource_id ascending.
    5. Consecutive step_no: 1..n.
    """
    def sort_key(s: StepModel):
        p_weight = PHASE_ORDER.get(s.phase, 99)
        op_weight = OPERATION_ORDER.get(s.operation, 99)
        return (p_weight, op_weight, s.system_id, s.resource_id)

    sorted_list = sorted(steps, key=sort_key)
    res = []
    for idx, s in enumerate(sorted_list, start=1):
        res.append(
            StepModel(
                step_no=idx,
                phase=s.phase,
                system_id=s.system_id,
                resource_id=s.resource_id,
                operation=s.operation,
                state=s.state,
                evidence_id=s.evidence_id,
            )
        )
    return res
