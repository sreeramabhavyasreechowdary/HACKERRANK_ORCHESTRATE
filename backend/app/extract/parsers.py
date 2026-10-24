"""Deterministic Evidence Parsers (Overrides 3, Milestone B3).

Parses structured evidence (CSV, SQL snapshot exports, JSON, logs, text, PDFs)
strictly in deterministic Python code without requiring LLM calls.
Loads SQL snapshots into an in-memory SQLite DB and queries them for records
matching the user's resolved identifiers.
"""

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field

from backend.app.ingest.identity import ResolvedIdentity


class ParsedRecord(BaseModel):
    """Normalized observation extracted from an evidence file."""
    file_id: str
    file_path: str
    system_id: str
    resource_id: str
    operation_hint: Optional[str] = None
    data_present: bool = True
    matched_field: str
    matched_value: str
    captured_at: Optional[str] = None
    record_details: Dict[str, Any] = Field(default_factory=dict)


class SQLSnapshotParser:
    """Loads SQL snapshot exports into an in-memory SQLite DB and queries matching records."""

    TABLE_TO_SYSTEM = {
        "customer_profiles": "account_service",
        "customer_profiles_primary": "account_service",
        "customer_profiles_failover_replica": "account_service",
        "customer_search_documents": "search_service",
        "customer_analytics_profiles": "analytics_platform",
        "support_records": "support_platform",
        "customer_exports": "export_service",
        "connector_subscriptions": "integration_service",
        "backup_restore_entries": "backup_service",
        "security_audit_records": "security_service",
        "customer_data_primary": "account_service",
        "customer_data_failover_replica": "account_service",
    }

    @classmethod
    def parse(cls, file_path: Path, file_id: str, identity: ResolvedIdentity, captured_at: Optional[str] = None) -> List[ParsedRecord]:
        results: List[ParsedRecord] = []
        if not file_path.exists():
            return results

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            sql_content = f.read()

        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(sql_content)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall() if r[0] != "snapshot_scope"]

            for table in tables:
                system_id = cls.TABLE_TO_SYSTEM.get(table, "account_service")
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [c[1] for c in cursor.fetchall()]

                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()

                for row in rows:
                    row_dict = dict(zip(cols, row))
                    res_id = str(row_dict.get("resource_id") or row_dict.get("id") or "")

                    # Check record_json if present (e.g. customer_data_primary)
                    if "record_json" in row_dict and row_dict["record_json"]:
                        try:
                            nested_json = json.loads(row_dict["record_json"])
                            row_dict.update(nested_json)
                            if "origin_system" in row_dict:
                                system_id = row_dict["origin_system"]
                            if "resource_id" in nested_json:
                                res_id = nested_json["resource_id"]
                        except Exception:
                            pass

                    # Check for identity matches across all column values
                    matched = False
                    matched_field = ""
                    matched_val = ""

                    for col_name, val in row_dict.items():
                        if val is None:
                            continue
                        val_str = str(val).strip()
                        val_lower = val_str.lower()

                        if val_lower in identity.all_terms or any(term in val_lower for term in identity.emails | identity.email_hashes if len(term) > 5):
                            matched = True
                            matched_field = col_name
                            matched_val = val_str
                            break

                    if matched and res_id:
                        # Determine system_id from resource prefix if available
                        if res_id.startswith("search_"):
                            system_id = "search_service"
                        elif res_id.startswith("support_"):
                            system_id = "support_platform"
                        elif res_id.startswith("analytics_"):
                            system_id = "analytics_platform"
                        elif res_id.startswith("audit_record_"):
                            system_id = "security_service"
                        elif res_id.startswith("data_flow_"):
                            system_id = "integration_service"
                        elif res_id.startswith("backup_"):
                            system_id = "backup_service"
                        elif res_id.startswith("export_"):
                            system_id = "export_service"
                        elif res_id.startswith("account_"):
                            system_id = "account_service"

                        results.append(
                            ParsedRecord(
                                file_id=file_id,
                                file_path=str(file_path),
                                system_id=system_id,
                                resource_id=res_id,
                                matched_field=matched_field,
                                matched_value=matched_val,
                                captured_at=captured_at or str(row_dict.get("updated_at", "")),
                                record_details=row_dict,
                            )
                        )
        except Exception:
            pass
        finally:
            conn.close()

        return results


class JSONSnapshotParser:
    """Parses JSON snapshot exports and bundles matching user identifiers."""

    @classmethod
    def parse(cls, file_path: Path, file_id: str, identity: ResolvedIdentity, captured_at: Optional[str] = None) -> List[ParsedRecord]:
        results: List[ParsedRecord] = []
        if not file_path.exists():
            return results

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Flatten bundles or nested lists
            record_list = []
            if isinstance(data, dict):
                if "snapshots" in data and isinstance(data["snapshots"], list):
                    for snap in data["snapshots"]:
                        store = snap.get("data_store", "account_service")
                        for rec in snap.get("records", []):
                            rec["_system_hint"] = store
                            record_list.append(rec)
                elif "records" in data and isinstance(data["records"], list):
                    source = data.get("origin") or data.get("source") or "account_service"
                    for rec in data["records"]:
                        rec["_system_hint"] = source
                        record_list.append(rec)
            elif isinstance(data, list):
                record_list = data

            for rec in record_list:
                if not isinstance(rec, dict):
                    continue

                res_id = str(rec.get("resource_id") or rec.get("id") or "")
                system_id = rec.get("_system_hint", "account_service")

                # Match identifiers
                matched = False
                matched_field = ""
                matched_val = ""

                for k, v in rec.items():
                    if k.startswith("_") or v is None:
                        continue
                    v_str = str(v).strip()
                    v_lower = v_str.lower()
                    if v_lower in identity.all_terms or any(term in v_lower for term in identity.emails | identity.email_hashes if len(term) > 5):
                        matched = True
                        matched_field = k
                        matched_val = v_str
                        break

                if matched and res_id:
                    if res_id.startswith("search_"):
                        system_id = "search_service"
                    elif res_id.startswith("support_"):
                        system_id = "support_platform"
                    elif res_id.startswith("analytics_"):
                        system_id = "analytics_platform"
                    elif res_id.startswith("audit_record_"):
                        system_id = "security_service"
                    elif res_id.startswith("data_flow_"):
                        system_id = "integration_service"
                    elif res_id.startswith("backup_"):
                        system_id = "backup_service"
                    elif res_id.startswith("export_"):
                        system_id = "export_service"
                    elif res_id.startswith("account_"):
                        system_id = "account_service"

                    results.append(
                        ParsedRecord(
                            file_id=file_id,
                            file_path=str(file_path),
                            system_id=system_id,
                            resource_id=res_id,
                            matched_field=matched_field,
                            matched_value=matched_val,
                            captured_at=captured_at or str(rec.get("updated_at", "")),
                            record_details=rec,
                        )
                    )
        except Exception:
            pass

        return results


class LogParser:
    """Parses application and service log files matching user identifiers."""

    @classmethod
    def parse(cls, file_path: Path, file_id: str, identity: ResolvedIdentity, captured_at: Optional[str] = None) -> List[ParsedRecord]:
        results: List[ParsedRecord] = []
        if not file_path.exists():
            return results

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    line_lower = line_str.lower()

                    matched = False
                    matched_val = ""
                    for term in identity.all_terms:
                        if len(term) > 3 and term in line_lower:
                            matched = True
                            matched_val = term
                            break

                    if matched:
                        # Extract resource ID if present in line
                        res_match = re.search(r'\b(account_\w+|search_\w+|support_\w+|analytics_\w+|audit_record_\w+|data_flow_\w+|backup_\w+|export_\w+)\b', line_str)
                        res_id = res_match.group(1) if res_match else f"log_record_{file_id}"

                        system_id = "account_service"
                        if "search" in res_id or "search_service" in line_str:
                            system_id = "search_service"
                        elif "support" in res_id or "support_platform" in line_str:
                            system_id = "support_platform"
                        elif "analytics" in res_id or "analytics_platform" in line_str:
                            system_id = "analytics_platform"
                        elif "audit_record" in res_id or "security_service" in line_str:
                            system_id = "security_service"
                        elif "data_flow" in res_id or "integration_service" in line_str:
                            system_id = "integration_service"
                        elif "backup" in res_id or "backup_service" in line_str:
                            system_id = "backup_service"

                        results.append(
                            ParsedRecord(
                                file_id=file_id,
                                file_path=str(file_path),
                                system_id=system_id,
                                resource_id=res_id,
                                matched_field="log_message",
                                matched_value=matched_val,
                                captured_at=captured_at,
                                record_details={"log_line": line_str[:300]},
                            )
                        )
        except Exception:
            pass

        return results


class PDFDocumentParser:
    """Deterministic PDF parser using pypdf."""

    @classmethod
    def parse(cls, file_path: Path, file_id: str, identity: ResolvedIdentity, captured_at: Optional[str] = None) -> List[ParsedRecord]:
        results: List[ParsedRecord] = []
        if not file_path.exists():
            return results

        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            full_text = "\n".join([page.extract_text() or "" for page in reader.pages])
            text_lower = full_text.lower()

            matched = False
            matched_val = ""
            for term in identity.all_terms:
                if len(term) > 3 and term in text_lower:
                    matched = True
                    matched_val = term
                    break

            if matched:
                res_match = re.search(r'\b(account_\w+|search_\w+|support_\w+|analytics_\w+|audit_record_\w+|data_flow_\w+|backup_\w+|export_\w+)\b', full_text)
                res_id = res_match.group(1) if res_match else f"pdf_ref_{file_id}"

                system_id = "account_service"
                if "support" in res_id or "support" in file_path.name:
                    system_id = "support_platform"
                elif "audit" in res_id or "security" in file_path.name:
                    system_id = "security_service"
                elif "export" in res_id or "history" in file_path.name:
                    system_id = "export_service"

                results.append(
                    ParsedRecord(
                        file_id=file_id,
                        file_path=str(file_path),
                        system_id=system_id,
                        resource_id=res_id,
                        matched_field="pdf_text",
                        matched_value=matched_val,
                        captured_at=captured_at,
                        record_details={"snippet": full_text[:300]},
                    )
                )
        except Exception:
            pass

        return results


class DeterministicParserEngine:
    """Unified entrypoint dispatching evidence files to deterministic parsers."""

    @classmethod
    def parse_file(cls, file_path: Path, file_id: str, identity: ResolvedIdentity, captured_at: Optional[str] = None) -> List[ParsedRecord]:
        suffix = file_path.suffix.lower()
        if suffix == ".sql":
            return SQLSnapshotParser.parse(file_path, file_id, identity, captured_at)
        elif suffix == ".json":
            return JSONSnapshotParser.parse(file_path, file_id, identity, captured_at)
        elif suffix in [".log", ".txt", ".csv"]:
            return LogParser.parse(file_path, file_id, identity, captured_at)
        elif suffix == ".pdf":
            return PDFDocumentParser.parse(file_path, file_id, identity, captured_at)
        return []
