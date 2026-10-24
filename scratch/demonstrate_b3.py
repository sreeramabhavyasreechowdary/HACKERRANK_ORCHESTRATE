"""Demonstration script for Milestone B3 (Evidence Reading).

Demonstrates:
1. Deterministic parsers for 3 SQL snapshots, 3 JSON files, 3 LOG files, 3 PDF/TXT files
2. Multimodal VLM/LLM extraction for 3 images/PDFs with caching and token/cost telemetry
"""

import json
import sys
import os
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ingest.identity import IdentityResolver

from backend.app.extract.parsers import (
    SQLSnapshotParser,
    JSONSnapshotParser,
    LogParser,
    PDFDocumentParser,
    DeterministicParserEngine,
)
from backend.app.extract.vlm_extractor import MultimodalVLMExtractor

# 1. Initialize IdentityResolver with sample users
identities_df = pd.read_csv("dataset/user_identities.csv")
audit_log_df = pd.read_csv("dataset/user_audit_log.csv")
resolver = IdentityResolver(identities_df, audit_log_df)

# Test subjects
sample_users = [
    "leila.haddad@yahoo.com",     # Leila Haddad (user_05)
    "ingrid.dahl@outlook.com",     # Ingrid Dahl (user_18)
    "priya.raman@gmail.com",       # Priya Raman (user_07)
    "daniel.m47291@outlook.com",   # Daniel M
    "ines.rousseau@outlook.com",   # Ines Rousseau
]

print("=== PART (a): DETERMINISTIC EVIDENCE PARSERS ===")

# --- 1. SQL Snapshot Files ---
print("\n--- 1. SQL SNAPSHOT EXPORTS (In-memory SQLite) ---")
sql_files = [
    ("dataset/evidence/databases/customer_accounts_failover_replica_20260902.sql", "evidence_54", "leila.haddad@yahoo.com"),
    ("dataset/evidence/databases/customer_data_inventory_20260213.sql", "evidence_11", "daniel.m47291@outlook.com"),
    ("dataset/evidence/databases/customer_data_inventory_20260213.sql", "evidence_11", "ines.rousseau@outlook.com"),
]

for fpath, fid, email in sql_files:
    identity = resolver.resolve(email)
    p = Path(fpath)
    records = SQLSnapshotParser.parse(p, fid, identity)
    print(f"\n[SQL File] {p.name} (File ID: {fid}) | Subject: {email} ({identity.user_id})")
    print(f"  Matched Records: {len(records)}")
    for r in records[:2]:
        print(f"  -> System: {r.system_id} | Resource: {r.resource_id} | Matched: {r.matched_field}='{r.matched_value}'")

# --- 2. JSON Snapshot Files ---
print("\n--- 2. JSON SNAPSHOT FILES ---")
json_files = [
    ("dataset/evidence/records/connector_configurations_20260812.json", "evidence_14", "jain.aditi@gmail.com"),
    ("dataset/evidence/records/customer_data_snapshot_bundle_20260131.json", "evidence_16", "aarav.r528@outlook.com"),
    ("dataset/evidence/records/customer_analytics_report_20260907.json", "evidence_18", "leila.haddad@yahoo.com"),
]

for fpath, fid, email in json_files:
    identity = resolver.resolve(email)
    p = Path(fpath)
    records = JSONSnapshotParser.parse(p, fid, identity)
    print(f"\n[JSON File] {p.name} (File ID: {fid}) | Subject: {email} ({identity.user_id})")
    print(f"  Matched Records: {len(records)}")
    for r in records[:2]:
        print(f"  -> System: {r.system_id} | Resource: {r.resource_id} | Matched: {r.matched_field}='{r.matched_value}'")

# --- 3. LOG Files ---
print("\n--- 3. LOG FILES ---")
log_files = [
    ("dataset/evidence/logs/service_events_ap_south_20260915.log", "evidence_01", "leila.haddad@yahoo.com"),
    ("dataset/evidence/logs/application_trace_ap_northeast_20260730.log", "evidence_12", "leila.haddad@yahoo.com"),
    ("dataset/evidence/logs/search_index_diagnostic_20260906.log", "evidence_08", "leila.haddad@yahoo.com"),
]

for fpath, fid, email in log_files:
    identity = resolver.resolve(email)
    p = Path(fpath)
    records = LogParser.parse(p, fid, identity)
    print(f"\n[LOG File] {p.name} (File ID: {fid}) | Subject: {email}")
    print(f"  Matched Records: {len(records)}")
    for r in records[:2]:
        print(f"  -> System: {r.system_id} | Resource: {r.resource_id} | Matched: {r.matched_field}='{r.matched_value}'")

# --- 4. PDF / TXT Files ---
print("\n--- 4. PDF & TXT DOCUMENTS ---")
doc_files = [
    ("dataset/evidence/documents/account_history_report_20260718.pdf", "evidence_25", "ingrid.dahl@outlook.com"),
    ("dataset/evidence/documents/delivery_correction_attachment.pdf", "evidence_27", "priya.raman@gmail.com"),
    ("dataset/evidence/records/customer_account_handover_20261001.txt", "evidence_03", "leila.haddad@yahoo.com"),
]

for fpath, fid, email in doc_files:
    identity = resolver.resolve(email)
    p = Path(fpath)
    records = DeterministicParserEngine.parse_file(p, fid, identity)
    print(f"\n[Document] {p.name} (File ID: {fid}) | Subject: {email}")
    print(f"  Matched Records: {len(records)}")
    for r in records[:2]:
        print(f"  -> System: {r.system_id} | Resource: {r.resource_id} | Matched: {r.matched_field}='{r.matched_value}'")


print("\n=== PART (b): MULTIMODAL VLM EXTRACTION ===")
vlm = MultimodalVLMExtractor(
    cache_db_path=Path("data_cache.sqlite3"),
    usage_jsonl_path=Path("runs/model_usage.jsonl"),
    model="gemini-2.5-flash",
    prompt_version="v1.0",
)

vlm_files = [
    ("dataset/evidence/images/account_admin_console_20260926.png", "evidence_04", "leila.haddad@yahoo.com"),
    ("dataset/evidence/images/search_index_inspector_20260901.png", "evidence_09", "leila.haddad@yahoo.com"),
    ("dataset/evidence/images/connector_management_console_20260807.png", "evidence_15", "ines.rousseau@outlook.com"),
]

for fpath, fid, email in vlm_files:
    p = Path(fpath)
    res = vlm.extract(p, fid, user_identifiers=[email], run_id="demo_b3")
    print(f"\n[VLM Image] {p.name} (File ID: {fid})")
    print(f"  Model: {res.model} | Cache hit: {res.is_cache_hit} | In tokens: {res.tokens_input} | Out tokens: {res.tokens_output} | Cost: ${res.cost_usd:.6f}")
    for obs in res.observations:
        print(f"  -> System: {obs.system_id} | Resource: {obs.resource_id} | Present: {obs.data_present}")
        print(f"     Literal: {obs.literal_description}")
        print(f"     Interpretation: {obs.interpretation}")

# Generate usage report
usage_report_path = MultimodalVLMExtractor.generate_usage_report(
    cache_db_path=Path("data_cache.sqlite3"),
    output_path=Path("evaluation/usage_report.md"),
    total_requests=32,
)
print(f"\nUsage report written to: {usage_report_path}")
