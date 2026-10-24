"""Data ingestion loader (FR-1, Hard Rule 1, Milestone B1).

Loads and validates all dataset CSV files.
Enforces strictly that prediction input loading NEVER reads sample_output.csv.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict


class DeletionRequest(BaseModel):
    """A single deletion audit request."""
    case_id: str
    email: str
    requested_at: str
    reported_status: str
    reported_at: str
    audit_at: str
    request_text: str


# Alias for state reconstruction backward compatibility
CaseRecord = DeletionRequest



class UserIdentity(BaseModel):
    user_id: str
    name: str
    email: str
    phone: str
    email_hash: str
    updated_at: str


class UserAuditRecord(BaseModel):
    audit_id: str
    user_id: str
    event_time: str
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class SystemActivityRecord(BaseModel):
    activity_id: str
    event_time: str
    event_type: str
    source_system: str
    target_system: str
    resource_id: Optional[str] = None
    reported_result: str
    details: Optional[str] = None


class DeletionRule(BaseModel):
    rule_id: str
    data_category: str
    condition: str
    required_action: str


class EvidenceFileManifest(BaseModel):
    file_id: str
    file_path: str
    origin: str
    captured_at: str


class DatasetBundle(BaseModel):
    """Container for loaded dataset files."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    requests: List[DeletionRequest]
    identities: List[UserIdentity]
    audit_log: List[UserAuditRecord]
    activities: List[SystemActivityRecord]
    rules: List[DeletionRule]
    evidence_manifest: List[EvidenceFileManifest]
    valid_citation_ids: Set[str] = Field(default_factory=set)


class DataLoader:
    """Loads and validates all challenge dataset CSVs."""

    EXPECTED_COLUMNS = {
        "deletion_requests": ["case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at", "request_text"],
        "user_identities": ["user_id", "name", "email", "phone", "email_hash", "updated_at"],
        "user_audit_log": ["audit_id", "user_id", "event_time", "field_name", "old_value", "new_value"],
        "system_activity": ["activity_id", "event_time", "event_type", "source_system", "target_system", "resource_id", "reported_result", "details"],
        "deletion_rules": ["rule_id", "data_category", "condition", "required_action"],
        "evidence_files": ["file_id", "file_path", "origin", "captured_at"],
    }

    @classmethod
    def validate_columns(cls, df: pd.DataFrame, expected: List[str], file_path: Path):
        """Confirm all expected columns exist in the DataFrame."""
        missing = [c for c in expected if c not in df.columns]
        if missing:
            raise ValueError(f"File {file_path.name} is missing expected columns: {missing}. Found: {list(df.columns)}")

    @classmethod
    def load_requests(cls, path: Path) -> List[DeletionRequest]:
        """Load requests file (sample or final). Strictly blocks sample_output.csv."""
        if "sample_output" in path.name.lower():
            raise PermissionError(
                f"Hard Rule 1 Violation: Ingestion path is strictly forbidden "
                f"from reading sample_output.csv ({path})"
            )

        if not path.exists():
            raise FileNotFoundError(f"Requests file not found: {path}")

        df = pd.read_csv(path)
        cls.validate_columns(df, cls.EXPECTED_COLUMNS["deletion_requests"], path)

        if df["case_id"].duplicated().any():
            dups = df[df["case_id"].duplicated()]["case_id"].tolist()
            raise ValueError(f"Duplicate case_id in {path}: {dups}")

        requests = []
        for _, row in df.iterrows():
            requests.append(
                DeletionRequest(
                    case_id=str(row["case_id"]).strip(),
                    email=str(row["email"]).strip(),
                    requested_at=str(row["requested_at"]).strip(),
                    reported_status=str(row["reported_status"]).strip(),
                    reported_at=str(row["reported_at"]).strip(),
                    audit_at=str(row["audit_at"]).strip(),
                    request_text=str(row["request_text"]) if pd.notna(row["request_text"]) else "",
                )
            )
        return requests

    # Backward-compatible alias
    load_cases = load_requests


    @classmethod
    def load_identities(cls, path: Path) -> List[UserIdentity]:
        """Load user_identities.csv."""
        df = pd.read_csv(path)
        cls.validate_columns(df, cls.EXPECTED_COLUMNS["user_identities"], path)
        return [
            UserIdentity(
                user_id=str(r["user_id"]).strip(),
                name=str(r["name"]).strip(),
                email=str(r["email"]).strip(),
                phone=str(r["phone"]).strip(),
                email_hash=str(r["email_hash"]).strip(),
                updated_at=str(r["updated_at"]).strip(),
            )
            for _, r in df.iterrows()
        ]

    @classmethod
    def load_audit_log(cls, path: Path) -> List[UserAuditRecord]:
        """Load user_audit_log.csv."""
        df = pd.read_csv(path)
        cls.validate_columns(df, cls.EXPECTED_COLUMNS["user_audit_log"], path)
        return [
            UserAuditRecord(
                audit_id=str(r["audit_id"]).strip(),
                user_id=str(r["user_id"]).strip(),
                event_time=str(r["event_time"]).strip(),
                field_name=str(r["field_name"]).strip(),
                old_value=str(r["old_value"]).strip() if pd.notna(r["old_value"]) else None,
                new_value=str(r["new_value"]).strip() if pd.notna(r["new_value"]) else None,
            )
            for _, r in df.iterrows()
        ]

    @classmethod
    def load_system_activity(cls, path: Path) -> List[SystemActivityRecord]:
        """Load system_activity.csv."""
        df = pd.read_csv(path)
        cls.validate_columns(df, cls.EXPECTED_COLUMNS["system_activity"], path)
        return [
            SystemActivityRecord(
                activity_id=str(r["activity_id"]).strip(),
                event_time=str(r["event_time"]).strip(),
                event_type=str(r["event_type"]).strip(),
                source_system=str(r["source_system"]).strip(),
                target_system=str(r["target_system"]).strip(),
                resource_id=str(r["resource_id"]).strip() if pd.notna(r["resource_id"]) else None,
                reported_result=str(r["reported_result"]).strip(),
                details=str(r["details"]).strip() if pd.notna(r["details"]) else None,
            )
            for _, r in df.iterrows()
        ]

    @classmethod
    def load_deletion_rules(cls, path: Path) -> List[DeletionRule]:
        """Load deletion_rules.csv."""
        df = pd.read_csv(path)
        cls.validate_columns(df, cls.EXPECTED_COLUMNS["deletion_rules"], path)
        return [
            DeletionRule(
                rule_id=str(r["rule_id"]).strip(),
                data_category=str(r["data_category"]).strip(),
                condition=str(r["condition"]).strip(),
                required_action=str(r["required_action"]).strip(),
            )
            for _, r in df.iterrows()
        ]

    @classmethod
    def load_evidence_manifest(cls, path: Path) -> List[EvidenceFileManifest]:
        """Load evidence_files.csv."""
        df = pd.read_csv(path)
        cls.validate_columns(df, cls.EXPECTED_COLUMNS["evidence_files"], path)
        return [
            EvidenceFileManifest(
                file_id=str(r["file_id"]).strip(),
                file_path=str(r["file_path"]).strip(),
                origin=str(r["origin"]).strip(),
                captured_at=str(r["captured_at"]).strip(),
            )
            for _, r in df.iterrows()
        ]

    @classmethod
    def load_dataset(cls, dataset_dir: Path, mode: str = "sample") -> DatasetBundle:
        """Load all files from dataset/ directory based on mode."""
        req_file = "sample_deletion_requests.csv" if mode == "sample" else "deletion_requests.csv"
        requests = cls.load_requests(dataset_dir / req_file)
        identities = cls.load_identities(dataset_dir / "user_identities.csv")
        audit_log = cls.load_audit_log(dataset_dir / "user_audit_log.csv")
        activities = cls.load_system_activity(dataset_dir / "system_activity.csv")
        rules = cls.load_deletion_rules(dataset_dir / "deletion_rules.csv")
        manifest = cls.load_evidence_manifest(dataset_dir / "evidence_files.csv")

        # Compile set of valid citation IDs (file_id, activity_id, audit_id)
        valid_citations = set()
        valid_citations.update(m.file_id for m in manifest)
        valid_citations.update(a.activity_id for a in activities)
        valid_citations.update(al.audit_id for al in audit_log)

        return DatasetBundle(
            requests=requests,
            identities=identities,
            audit_log=audit_log,
            activities=activities,
            rules=rules,
            evidence_manifest=manifest,
            valid_citation_ids=valid_citations,
        )
