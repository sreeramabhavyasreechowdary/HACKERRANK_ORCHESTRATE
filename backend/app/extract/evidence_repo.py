"""Evidence Repository & Observation Index (Milestone B3/B4).

Deterministically indexes all structured evidence files (JSON, LOG, TXT, SQL, PDF)
into queryable evidence observations.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
import pandas as pd
from pydantic import BaseModel, Field

from backend.app.ingest.identity import ResolvedIdentity


class EvidenceObservation(BaseModel):
    file_id: str
    captured_at: str
    system_id: str
    resource_id: str
    category: str
    status: str  # ABSENT, PRESENT, EXPOSED, ANONYMIZED, REDACTED, ACTIVE, DISABLED, BLOCKED
    user_identifiers: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class EvidenceRepository:
    """Indexes all evidence files deterministically into queryable observations."""

    def __init__(self, manifest_df: pd.DataFrame, base_dir: Path = Path("dataset")):
        self.manifest_df = manifest_df
        self.base_dir = base_dir
        self.observations: List[EvidenceObservation] = []
        self._load_all()

    def _load_all(self):
        for _, row in self.manifest_df.iterrows():
            fid = row["file_id"]
            fpath = self.base_dir / row["file_path"]
            cap = str(row["captured_at"])
            origin = str(row["origin"])
            if not fpath.exists():
                continue
            sfx = fpath.suffix.lower()
            if sfx == ".json":
                self._load_json(fid, fpath, cap, origin)
            elif sfx == ".txt":
                self._load_txt(fid, fpath, cap, origin)
            elif sfx == ".log":
                self._load_log(fid, fpath, cap, origin)
            elif sfx == ".sql":
                self._load_sql(fid, fpath, cap, origin)
            elif sfx == ".pdf":
                self._load_pdf(fid, fpath, cap, origin)

    def _load_pdf(self, fid: str, fpath: Path, cap: str, origin: str):
        try:
            import pypdf
            reader = pypdf.PdfReader(str(fpath))
            full_text = "\n".join([page.extract_text() or "" for page in reader.pages])
            text_lower = full_text.lower()

            m_res = re.search(r"\b(support_\w+|account_\w+|export_\w+)\b", full_text)
            res_id = m_res.group(1) if m_res else f"attachment_{fid}"

            # Extract emails and names
            emails = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text_lower)
            sys_id = "support_platform" if "support" in res_id or "delivery" in text_lower else "account_service"
            cat = "SUPPORT_ATTACHMENT" if "support" in res_id or "delivery" in text_lower else "USER_PROFILE"

            self.observations.append(
                EvidenceObservation(
                    file_id=fid,
                    captured_at=cap,
                    system_id=sys_id,
                    resource_id=res_id,
                    category=cat,
                    status="PRESENT",
                    user_identifiers=emails,
                    details={"extracted_text": full_text[:300]},
                )
            )
        except Exception:
            pass

    def _load_txt(self, fid: str, fpath: Path, cap: str, origin: str):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith("- "):
                        continue
                    parts = [p.strip() for p in line[2:].split("|")]
                    if len(parts) >= 6:
                        t_str, sys_id, res_id, cat, stat, ident_str = parts[:6]
                        norm_stat = "UNKNOWN"
                        if stat == "NOT_FOUND":
                            norm_stat = "ABSENT"
                        elif stat == "FOUND":
                            norm_stat = "PRESENT"
                        elif stat == "IDENTIFIABLE":
                            norm_stat = "EXPOSED"
                        elif stat == "ANONYMIZED":
                            norm_stat = "ANONYMIZED"
                        elif stat == "REDACTED":
                            norm_stat = "REDACTED"
                        elif stat == "ACTIVE":
                            norm_stat = "ACTIVE"
                        elif stat == "DISABLED":
                            norm_stat = "DISABLED"
                        elif stat == "BLOCKED":
                            norm_stat = "BLOCKED"

                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                captured_at=cap,
                                system_id=sys_id,
                                resource_id=res_id,
                                category=cat,
                                status=norm_stat,
                                user_identifiers=[ident_str.strip().lower()],
                            )
                        )
        except Exception:
            pass

    def _load_json(self, fid: str, fpath: Path, cap: str, origin: str):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                d = json.load(f)
        except Exception:
            return

        if not isinstance(d, dict):
            return

        # 1. service_resource_export
        if "service_exports" in d:
            se = d["service_exports"]
            # account_service
            if "account_service" in se and "profile_lookups" in se["account_service"]:
                for pl in se["account_service"]["profile_lookups"]:
                    res_id = pl.get("resource_id")
                    code = pl.get("status_code")
                    prof = pl.get("profile")
                    idents = []
                    if prof and isinstance(prof, dict):
                        for k, v in prof.items():
                            if v:
                                idents.append(str(v).strip().lower())
                    stat = "ABSENT" if code == 404 or prof is None else "PRESENT"
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="account_service",
                            resource_id=res_id,
                            category="USER_PROFILE",
                            status=stat,
                            user_identifiers=idents,
                            details=pl,
                        )
                    )
            # search_service
            if "search_service" in se and "index_queries" in se["search_service"]:
                for iq in se["search_service"]["index_queries"]:
                    res_id = iq.get("resource_id")
                    hits = iq.get("hits", {})
                    total = hits.get("total", 0)
                    query = iq.get("query", "")
                    idents = [query.lower()] if query else []
                    if hits.get("documents"):
                        for doc in hits["documents"]:
                            for k, v in doc.items():
                                if v and k != "resource_id":
                                    idents.append(str(v).strip().lower())
                    stat = "PRESENT" if total > 0 else "ABSENT"
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="search_service",
                            resource_id=res_id,
                            category="SEARCH_INDEX_ENTRY",
                            status=stat,
                            user_identifiers=idents,
                            details=iq,
                        )
                    )
            # analytics_platform
            if "analytics_platform" in se and "profiles" in se["analytics_platform"]:
                for prof in se["analytics_platform"]["profiles"]:
                    res_id = prof.get("resource_id")
                    cref = prof.get("customer_reference")
                    email = prof.get("email")
                    phone = prof.get("phone")
                    ehash = prof.get("email_hash")
                    idents = [str(x).lower() for x in [cref, email, phone, ehash] if x]
                    has_pii = bool(email or phone or ehash)
                    stat = "EXPOSED" if has_pii else "ANONYMIZED"
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="analytics_platform",
                            resource_id=res_id,
                            category="ANALYTICS_PROFILE",
                            status=stat,
                            user_identifiers=idents,
                            details=prof,
                        )
                    )
            # support_platform
            if "support_platform" in se and "tickets" in se["support_platform"]:
                for tick in se["support_platform"]["tickets"]:
                    res_id = tick.get("resource_id")
                    cref = tick.get("customer_reference")
                    remail = tick.get("requester_email")
                    rname = tick.get("requester_name")
                    rphone = tick.get("requester_phone")
                    idents = [str(x).lower() for x in [cref, remail, rname, rphone] if x]
                    has_pii = bool(remail or rname or rphone)
                    stat = "EXPOSED" if has_pii else "REDACTED"
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="support_platform",
                            resource_id=res_id,
                            category="SUPPORT_MESSAGE",
                            status=stat,
                            user_identifiers=idents,
                            details=tick,
                        )
                    )
            # integration_service
            if "integration_service" in se and "connectors" in se["integration_service"]:
                for conn in se["integration_service"]["connectors"]:
                    res_id = conn.get("resource_id")
                    cref = conn.get("customer_reference")
                    cemail = conn.get("customer_email")
                    idents = [str(x).lower() for x in [cref, cemail] if x]
                    enabled = conn.get("enabled", False)
                    stat = "ACTIVE" if enabled else "DISABLED"
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="integration_service",
                            resource_id=res_id,
                            category="DATA_FLOW",
                            status=stat,
                            user_identifiers=idents,
                            details=conn,
                        )
                    )
            # backup_service
            if "backup_service" in se and "restore_entries" in se["backup_service"]:
                for be in se["backup_service"]["restore_entries"]:
                    res_id = be.get("resource_id")
                    cref = be.get("customer_reference")
                    cemail = be.get("customer_email")
                    idents = [str(x).lower() for x in [cref, cemail] if x]
                    allowed = be.get("restore_allowed", False)
                    stat = "ACTIVE" if allowed else "BLOCKED"
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="backup_service",
                            resource_id=res_id,
                            category="BACKUP_ARCHIVE",
                            status=stat,
                            user_identifiers=idents,
                            details=be,
                        )
                    )
            # security_service
            if "security_service" in se and "audit_records" in se["security_service"]:
                for ar in se["security_service"]["audit_records"]:
                    res_id = ar.get("resource_id")
                    sref = ar.get("subject_reference")
                    idents = [str(sref).lower()] if sref else []
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="security_service",
                            resource_id=res_id,
                            category="SECURITY_AUDIT_LOG",
                            status="PRESENT",
                            user_identifiers=idents,
                            details=ar,
                        )
                    )
            # export_service
            if "export_service" in se and "exports" in se["export_service"]:
                for exp in se["export_service"]["exports"]:
                    res_id = exp.get("resource_id")
                    oemail = exp.get("owner_email")
                    cref = exp.get("customer_reference")
                    idents = [str(x).lower() for x in [oemail, cref] if x]
                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id="export_service",
                            resource_id=res_id,
                            category="USER_EXPORT",
                            status="PRESENT",
                            user_identifiers=idents,
                            details=exp,
                        )
                    )

        # 2. records_assurance_snapshot_bundle
        if "snapshots" in d:
            for snap in d["snapshots"]:
                store = snap.get("data_store", "")
                coll = snap.get("collection", "")
                recs = snap.get("records", [])
                for rec in recs:
                    res_id = rec.get("resource_id")
                    if not res_id:
                        continue
                    idents = []
                    for k, v in rec.items():
                        if v and k != "resource_id":
                            idents.append(str(v).strip().lower())
                    if coll == "deleted_customer_references" or store == "identity_service":
                        has_pii = bool(rec.get("name") or rec.get("email") or rec.get("phone") or rec.get("email_hash"))
                        stat = "EXPOSED" if has_pii else "REDACTED"
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                captured_at=cap,
                                system_id="identity_service",
                                resource_id=res_id,
                                category="ACCOUNT_TOMBSTONE",
                                status=stat,
                                user_identifiers=idents,
                                details=rec,
                            )
                        )
                    elif coll == "customer_profiles" or store == "account_service":
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                captured_at=cap,
                                system_id="account_service",
                                resource_id=res_id,
                                category="USER_PROFILE",
                                status="PRESENT",
                                user_identifiers=idents,
                                details=rec,
                            )
                        )
                    elif coll == "security_audit_events" or store == "security_service":
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                captured_at=cap,
                                system_id="security_service",
                                resource_id=res_id,
                                category="SECURITY_AUDIT_LOG",
                                status="PRESENT",
                                user_identifiers=idents,
                                details=rec,
                            )
                        )
                    elif coll == "customer_search_documents" or store == "search_service":
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                captured_at=cap,
                                system_id="search_service",
                                resource_id=res_id,
                                category="SEARCH_INDEX_ENTRY",
                                status="PRESENT",
                                user_identifiers=idents,
                                details=rec,
                            )
                        )
                    elif coll == "customer_export_jobs" or store == "export_service":
                        self.observations.append(
                            EvidenceObservation(
                                file_id=fid,
                                captured_at=cap,
                                system_id="export_service",
                                resource_id=res_id,
                                category="USER_EXPORT",
                                status="PRESENT",
                                user_identifiers=idents,
                                details=rec,
                            )
                        )

        # 3. Top-level records (e.g. customer_export_jobs, customer_analytics_reports)
        if "records" in d and isinstance(d["records"], list):
            source = d.get("source") or d.get("origin") or ""
            collection = d.get("collection") or ""
            for rec in d["records"]:
                res_id = rec.get("resource_id") or rec.get("id")
                if not res_id:
                    continue
                idents = []
                for k, v in rec.items():
                    if v and k not in ["resource_id", "id", "metrics", "recent_activity"]:
                        idents.append(str(v).strip().lower())

                sys_id = "account_service"
                cat = "USER_PROFILE"
                stat = "PRESENT"

                if "export" in collection or "export" in source or res_id.startswith("export_"):
                    sys_id = "export_service"
                    cat = "USER_EXPORT"
                    stat = "PRESENT"
                elif "analytics" in collection or "analytics" in source or res_id.startswith("analytics_"):
                    sys_id = "analytics_platform"
                    cat = "ANALYTICS_PROFILE"
                    has_pii = bool(rec.get("email") or rec.get("phone") or rec.get("email_hash"))
                    stat = "EXPOSED" if has_pii else "ANONYMIZED"
                elif "connector" in collection or res_id.startswith("data_flow_"):
                    sys_id = "integration_service"
                    cat = "DATA_FLOW"
                    stat = "ACTIVE" if rec.get("enabled", False) else "DISABLED"
                elif "audit" in collection or res_id.startswith("audit_record_"):
                    sys_id = "security_service"
                    cat = "SECURITY_AUDIT_LOG"
                    stat = "PRESENT"

                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        captured_at=cap,
                        system_id=sys_id,
                        resource_id=str(res_id),
                        category=cat,
                        status=stat,
                        user_identifiers=idents,
                        details=rec,
                    )
                )

    def _load_log(self, fid: str, fpath: Path, cap: str, origin: str):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return

        # Group lines by trace_id
        traces: Dict[str, List[str]] = {}
        untraced_lines: List[str] = []

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            m_trace = re.search(r"trace_id=([a-zA-Z0-9_\-]+)", line_str)
            if m_trace:
                tid = m_trace.group(1)
                traces.setdefault(tid, []).append(line_str)
            else:
                untraced_lines.append(line_str)

        # Process each trace group
        trace_groups = list(traces.values()) + [[l] for l in untraced_lines]
        for lines in trace_groups:
            full_text = " \n ".join(lines)
            m_res = re.search(r"resource_id=([a-zA-Z0-9_]+)", full_text)
            if not m_res:
                continue
            res_id = m_res.group(1)

            m_srv = re.search(r"service=([a-zA-Z0-9_]+)", full_text)
            srv = m_srv.group(1) if m_srv else "account_service"

            # Extract all identifiers in trace
            idents = set()
            for pattern in [
                r'lookup_key="?([^"\s]+)"?',
                r'subject_key="?([^"\s]+)"?',
                r'correlation_key="?([^"\s]+)"?',
                r'customer_reference="?([^"\s]+)"?',
                r'subject_reference="?([^"\s]+)"?',
                r'subject_ref="?([^"\s]+)"?',
                r'matched_value="?([^"\s]+)"?',
                r'email="?([^"\s]+)"?',
            ]:
                for match in re.finditer(pattern, full_text):
                    val = match.group(1).strip('"').lower()
                    if val and val != "null":
                        idents.add(val)

            stat = "UNKNOWN"
            cat = "USER_PROFILE"

            if "support" in srv or "support" in res_id:
                srv = "support_platform"
                cat = "SUPPORT_MESSAGE"
                if "message_pii_scan" in full_text:
                    stat = "EXPOSED"
                elif "rows=1" in full_text or "marker_found=false" in full_text:
                    stat = "PRESENT"
                elif "requester_email=null" in full_text:
                    stat = "REDACTED"
            elif srv == "account_service":
                cat = "USER_PROFILE"
                if "rows=0" in full_text or "http_status=404" in full_text:
                    stat = "ABSENT"
                elif "rows=1" in full_text or "http_status=200" in full_text:
                    stat = "PRESENT"
            elif srv == "search_service":
                cat = "SEARCH_INDEX_ENTRY"
                if "result=hit" in full_text or "total_hits=1" in full_text:
                    stat = "PRESENT"
                elif "result=miss" in full_text or "total_hits=0" in full_text:
                    stat = "ABSENT"
            elif srv == "security_service":
                cat = "SECURITY_AUDIT_LOG"
                stat = "PRESENT"
            elif srv == "analytics_platform":
                cat = "ANALYTICS_PROFILE"
                if "contact_lookup_completed" in full_text:
                    cat = "SECONDARY_IDENTIFIER"
                    stat = "PRESENT"
                elif "rows=1" in full_text or ("email=" in full_text and not "email=null" in full_text):
                    stat = "EXPOSED"
                else:
                    stat = "ANONYMIZED"
            elif srv == "integration_service":
                cat = "DATA_FLOW"
                enabled = "enabled=true" in full_text
                stat = "ACTIVE" if enabled else "DISABLED"
            elif srv == "backup_service":
                cat = "BACKUP_ARCHIVE"
                allowed = "restore_allowed=true" in full_text or "eligible=true" in full_text or "deletion_block=false" in full_text
                stat = "ACTIVE" if allowed else "BLOCKED"

            if stat != "UNKNOWN":
                self.observations.append(
                    EvidenceObservation(
                        file_id=fid,
                        captured_at=cap,
                        system_id=srv,
                        resource_id=res_id,
                        category=cat,
                        status=stat,
                        user_identifiers=list(idents),
                        details={"trace_lines": lines[:3]},
                    )
                )

    def _extract_nested_strings(self, obj: Any) -> List[str]:
        """Recursively extract all string values from nested dicts/lists."""
        res: List[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k not in ["resource_id", "metrics", "recent_activity", "reporting_window"]:
                    res.extend(self._extract_nested_strings(v))
        elif isinstance(obj, list):
            for item in obj:
                res.extend(self._extract_nested_strings(item))
        elif obj is not None:
            s = str(obj).strip().lower()
            if s and s not in ["null", "none", "true", "false"]:
                res.append(s)
        return res

    def _load_sql(self, fid: str, fpath: Path, cap: str, origin: str):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return

        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(content)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            for tbl in tables:
                cur.execute(f"PRAGMA table_info({tbl})")
                cols = [c[1] for c in cur.fetchall()]
                cur.execute(f"SELECT * FROM {tbl}")
                rows = cur.fetchall()
                for r in rows:
                    rd = dict(zip(cols, r))
                    res_id = rd.get("resource_id") or rd.get("id")
                    if not res_id:
                        continue

                    # If record_json is present, parse nested json
                    if "record_json" in rd and rd["record_json"]:
                        try:
                            nested = json.loads(rd["record_json"])
                            orig_sys = rd.get("origin_system", "account_service")
                            cat = "USER_PROFILE"
                            stat = "PRESENT"
                            nested_idents = self._extract_nested_strings(nested)

                            if orig_sys == "analytics_platform":
                                cat = "ANALYTICS_PROFILE"
                                has_pii = bool(nested.get("email") or nested.get("phone") or nested.get("email_hash"))
                                stat = "EXPOSED" if has_pii else "ANONYMIZED"
                            elif orig_sys == "security_service":
                                cat = "SECURITY_AUDIT_LOG"
                                stat = "PRESENT"
                            elif orig_sys == "search_service":
                                cat = "SEARCH_INDEX_ENTRY"
                                stat = "PRESENT"

                            self.observations.append(
                                EvidenceObservation(
                                    file_id=fid,
                                    captured_at=cap,
                                    system_id=orig_sys,
                                    resource_id=str(nested.get("resource_id", res_id)),
                                    category=cat,
                                    status=stat,
                                    user_identifiers=nested_idents,
                                    details=nested,
                                )
                            )
                            continue
                        except Exception:
                            pass

                    idents = [str(v).strip().lower() for v in rd.values() if v and str(v) != str(res_id)]
                    sys_id = "account_service"
                    cat = "USER_PROFILE"
                    stat = "PRESENT"

                    if "search" in tbl or str(res_id).startswith("search_"):
                        sys_id = "search_service"
                        cat = "SEARCH_INDEX_ENTRY"
                    elif "backup" in tbl or str(res_id).startswith("backup_"):
                        sys_id = "backup_service"
                        cat = "BACKUP_ARCHIVE"
                        stat = "ACTIVE"  # default active backup finding unless blocked

                    self.observations.append(
                        EvidenceObservation(
                            file_id=fid,
                            captured_at=cap,
                            system_id=sys_id,
                            resource_id=str(res_id),
                            category=cat,
                            status=stat,
                            user_identifiers=idents,
                            details=rd,
                        )
                    )
        except Exception:
            pass
        finally:
            conn.close()

    def find_observations_for_identity(
        self,
        identity: ResolvedIdentity,
        max_time: Optional[str] = None,
        linked_resource_ids: Optional[Set[str]] = None,
    ) -> List[EvidenceObservation]:
        """Query matching observations captured on or before max_time."""
        matched: List[EvidenceObservation] = []
        user_terms = identity.all_terms
        resource_set = linked_resource_ids or set()

        for obs in self.observations:
            if max_time and obs.captured_at > max_time:
                continue

            # Match by linked resource_id
            if obs.resource_id in resource_set:
                matched.append(obs)
                continue

            # Match by user identifier terms strictly
            is_match = False
            for term in user_terms:
                t_clean = term.strip().lower()
                if not t_clean:
                    continue
                for uid in obs.user_identifiers:
                    u_clean = uid.strip().lower()
                    if not u_clean:
                        continue
                    if t_clean == u_clean:
                        is_match = True
                        break
                    # If term is an email, exact match only
                    if "@" in t_clean or "@" in u_clean:
                        if t_clean == u_clean:
                            is_match = True
                            break
                    # If term is a user_id (e.g. user_10), exact match only
                    elif t_clean.startswith("user_") or u_clean.startswith("user_"):
                        if t_clean == u_clean:
                            is_match = True
                            break
                    # Otherwise, require word boundary or min length
                    elif len(t_clean) > 5 and (f" {t_clean} " in f" {u_clean} "):
                        is_match = True
                        break
                if is_match:
                    break

            if is_match:
                matched.append(obs)

        return matched
