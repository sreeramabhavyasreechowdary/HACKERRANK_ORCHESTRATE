# SPEC_NOTES.md — Ghost Data Still Exists

Status: **Locked & Grounded on Official Dataset & Problem Statement**
Last Updated: 2026-10-24

---

## 1. output.csv Schema and Constraints

- **Exact columns, in order**:
  ```csv
  case_id,deletion_status,steps_json
  ```
- **Total Rows**: Exactly 518 data rows in final mode (one per row in `dataset/deletion_requests.csv`), sorted strictly by `case_id` ascending.
- **Allowed `deletion_status` Values**:
  - `COMPLETE`: Deletion confirmed across all stores; only policy-retained records remain; no active recreation risks; `steps_json` contains only `VERIFICATION` phase steps with non-empty `evidence_id`.
  - `INCOMPLETE`: Unredacted data, missing deletions, or active recreation risks remain; `steps_json` contains `FINDING` steps (with citations), followed by `REMEDIATION` steps (`evidence_id=""`), followed by post-remediation `VERIFICATION` steps (`evidence_id=""`).
  - `NOT_APPLICABLE`: Subject did not request deletion (e.g. inquiry or classification as non-deletion); `steps_json` is strictly an empty JSON array: `[]`.
- **Step Structure (Exactly 7 keys)**:
  ```json
  {
    "step_no": 1,
    "phase": "FINDING",
    "system_id": "account_service",
    "resource_id": "account_005",
    "operation": "REPORT_REMAINING_RECORD",
    "state": "PRESENT",
    "evidence_id": "evidence_01"
  }
  ```
- **The 15 Allowed (Phase, Operation, State) Triples**:
  1. `(FINDING, REPORT_REMAINING_RECORD, PRESENT)`
  2. `(FINDING, REPORT_EXPOSED_PII, PRESENT)`
  3. `(FINDING, REPORT_ACTIVE_DATA_FLOW, ACTIVE)`
  4. `(FINDING, REPORT_RESTORE_RISK, ACTIVE)`
  5. `(REMEDIATION, DISABLE_DATA_FLOW, DISABLED)`
  6. `(REMEDIATION, BLOCK_RESTORE, BLOCKED)`
  7. `(REMEDIATION, DELETE_RECORD, ABSENT)`
  8. `(REMEDIATION, REDACT_RECORD, REDACTED)`
  9. `(REMEDIATION, ANONYMIZE_RECORD, ANONYMIZED)`
  10. `(VERIFICATION, VERIFY_RECORD_ABSENT, ABSENT)`
  11. `(VERIFICATION, VERIFY_RECORD_PRESENT, PRESENT)`
  12. `(VERIFICATION, VERIFY_RECORD_REDACTED, REDACTED)`
  13. `(VERIFICATION, VERIFY_RECORD_ANONYMIZED, ANONYMIZED)`
  14. `(VERIFICATION, VERIFY_DATA_FLOW_DISABLED, DISABLED)`
  15. `(VERIFICATION, VERIFY_RESTORE_BLOCKED, BLOCKED)`
- **Step Ordering Rules (Array order is significant)**:
  1. Phase order: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
  2. Within each phase: operation order matching the table above.
  3. Within each operation: `system_id` ascending.
  4. Within each `system_id`: `resource_id` ascending.
  5. `step_no` is consecutive 1..n.

---

## 2. Input Files Manifest (`dataset/`)

| File | Purpose | Rows | Key Columns |
|---|---|---|---|
| `deletion_requests.csv` | Full audit request set (Final Mode) | 518 | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text` |
| `sample_deletion_requests.csv` | Sample requests (Sample Mode) | 32 | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text` |
| `sample_output.csv` | Ground truth reference (Evaluator only) | 32 | `case_id,deletion_status,steps_json` |
| `user_identities.csv` | Current user profile identities | 850 | `user_id,name,email,phone,email_hash,updated_at` |
| `user_audit_log.csv` | Historical user identity updates | 306 | `audit_id,user_id,event_time,field_name,old_value,new_value` |
| `system_activity.csv` | Operational logs & lifecycle events | 4011 | `activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details` |
| `deletion_rules.csv` | Policy rules mapping category to action | 15 | `rule_id,data_category,condition,required_action` |
| `evidence_files.csv` | Manifest of evidence files | 94 | `file_id,file_path,origin,captured_at` |
| `output.csv` | Submission template | 0 | `case_id,deletion_status,steps_json` |
| `dataset/evidence/` | Raw evidence storage | 94 files | `.json` (28), `.log` (26), `.sql` (24), `.png` (11), `.pdf` (4), `.txt` (1) |

---

## 3. Deletion Policies Summary (`deletion_rules.csv`)

| Rule ID | Data Category | Condition | Required Action |
|---|---|---|---|
| `rule_01` | `USER_PROFILE` | Always | `DELETE` |
| `rule_02` | `SECONDARY_IDENTIFIER` | Always | `DELETE` |
| `rule_03` | `SEARCH_INDEX_ENTRY` | Always | `DELETE` |
| `rule_04` | `CACHE_ENTRY` | Always | `DELETE` |
| `rule_05` | `SUPPORT_MESSAGE` | Conversation contains shared context that must be retained | `REDACT` |
| `rule_06` | `SUPPORT_ATTACHMENT` | Attachment belongs only to the deletion subject | `DELETE` |
| `rule_07` | `ANALYTICS_PROFILE` | Record is still attributable to a user | `ANONYMIZE` |
| `rule_08` | `PRODUCT_TELEMETRY` | Record is still attributable to a user | `ANONYMIZE` |
| `rule_09` | `USER_EXPORT` | Always | `DELETE` |
| `rule_10` | `MARKETING_PROFILE` | Always | `DELETE` |
| `rule_11` | `EMAIL_DELIVERY_LOG` | Log contains a user email address | `REDACT` |
| `rule_12` | `SECURITY_AUDIT_LOG` | Record is within supplied retention period | `RETAIN` |
| `rule_13` | `LEGAL_HOLD_RECORD` | A supplied legal hold is active | `RETAIN` |
| `rule_14` | `BACKUP_ARCHIVE` | Restore access can be blocked | `RETAIN` |
| `rule_15` | `ACCOUNT_TOMBSTONE` | Account is deleted & stable internal user_id needed | `REDACT` |

---

## 4. Evidence Parsing & Multimodal Strategy

- **Deterministic Code Parsing (79 files, 84.0%)**:
  - `JSON` (28 files): Parse bundles and customer data inventories deterministically.
  - `LOG` (26 files): Regex and structured text search for user identifiers, timestamps, and service events.
  - `SQL` (24 files): SQLite-compatible read-replica and failover snapshots, loaded into in-memory SQLite and queried via standard SQL.
  - `TXT` (1 file): Customer account handover note parsed via regex.
- **Multimodal VLM/LLM Extraction (15 files, 16.0%)**:
  - `PNG` (11 files): Screenshots of admin portals (account admin, search index, integration admin). VLM extracts structured observation JSON.
  - `PDF` (4 files): Support delivery confirmations and attachments. Parsed via text extraction fallback to vision.

---

## 11. Section 11: Real Facts from Dataset Reconnaissance

### 11.1 File Metrics
- `dataset/deletion_requests.csv`: Exactly 518 cases.
- `dataset/sample_deletion_requests.csv`: Exactly 32 cases.
- `dataset/sample_output.csv`: Exactly 32 cases (22 `INCOMPLETE`, 10 `COMPLETE`, 0 `NOT_APPLICABLE` in sample set; 10 `NOT_APPLICABLE` cases identified in full dataset via `CLASSIFY_REQUEST` events in `system_activity.csv`).
- `dataset/user_identities.csv`: 850 user records (`user_id,name,email,phone,email_hash,updated_at`).
- `dataset/user_audit_log.csv`: 306 historical update events across 196 users (107 email changes, 107 email_hash changes, 92 phone changes).
- `dataset/system_activity.csv`: 4011 activity records across 11 source systems and 19 target systems.
- `dataset/evidence_files.csv`: 94 declared evidence files across 30 origins.
- `dataset/evidence/` disk storage: Exactly 94 physical files matching the manifest.

### 11.2 Evidence Linking Mechanism
- `evidence_files.csv` contains system-wide snapshots and observability exports, **not per-case files**.
- Linking to a case requires resolving all current and historical identifiers for the subject:
  1. Retrieve `email` from `deletion_requests.csv`.
  2. Match `user_id`, `name`, `phone`, `email_hash` from `user_identities.csv`.
  3. Expand with previous `email`, `phone`, `email_hash` from `user_audit_log.csv`.
  4. Match records in evidence snapshots where any identifier appears on or before `audit_at`.

### 11.3 System IDs and Resource IDs
From `sample_output.csv` and `system_activity.csv`, system IDs map cleanly to resource ID prefixes:
- `account_service`: `account_001` .. `account_9999`
- `search_service`: `search_001` .. `search_9999`
- `support_platform`: `support_001` .. `support_9999`
- `analytics_platform`: `analytics_001` .. `analytics_9999`
- `security_service`: `audit_record_001` .. `audit_record_9999`
- `integration_service`: `data_flow_001` .. `data_flow_9999`
- `backup_service`: `backup_001` .. `backup_9999`
- `export_service`: `export_001` .. `export_9999`
- `identity_service`: `tombstone_001` .. `tombstone_9999`
- `marketing_platform`: `marketing_001` .. `marketing_9999`

### 11.4 Sample Output Observed Patterns
- **`COMPLETE` Cases (10 cases in sample)**:
  - Step counts range from 1 to 6 (mean: 3.4, median: 3.0).
  - Contain **ONLY** `VERIFICATION` phase steps.
  - Every single verification step cites a valid `file_id` (e.g. `evidence_54`, `evidence_94`). 34 out of 34 steps cite an evidence file (100%).
  - Operations observed: `VERIFY_RECORD_ABSENT` (10), `VERIFY_RECORD_PRESENT` (7), `VERIFY_RECORD_ANONYMIZED` (7), `VERIFY_RECORD_REDACTED` (4), `VERIFY_DATA_FLOW_DISABLED` (3), `VERIFY_RESTORE_BLOCKED` (3).
- **`INCOMPLETE` Cases (22 cases in sample)**:
  - Step counts range from 3 to 14 (mean: 7.2, median: 6.0).
  - Contain `FINDING` steps, followed by `REMEDIATION` steps, followed by `VERIFICATION` steps.
  - 1-to-1 match between findings and remediations (41 findings, 41 remediations).
  - Citations in `FINDING`: 41 out of 41 cite a `file_id` (100%).
  - Citations in `REMEDIATION`: 0 out of 41 cite evidence (always `""`).
  - Citations in `VERIFICATION` for incomplete cases: 0 out of 77 cite evidence (always `""`, because these represent prospective checks that must pass after remediation).
- **`NOT_APPLICABLE` Cases**:
  - `steps_json` is strictly `[]`.

---

## 12. Section 12: Resolution of Open Questions

1. **What are the exact output.csv columns and allowed verdict values?**
   - **Resolved**: Columns are `case_id,deletion_status,steps_json`. Verdicts are strictly `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`.
2. **What is the citation format?**
   - **Resolved**: Evidence citations are strings containing the `file_id` from `evidence_files.csv` (e.g. `evidence_54`). Remediations and incomplete verifications use empty string `""`.
3. **How does evidence link to cases?**
   - **Resolved**: Resolved via identity attributes (`email`, `user_id`, `phone`, `name`, `email_hash` across current identities and audit logs) found within evidence files captured on or before `audit_at`.
4. **How are structured vs multimodal evidence handled?**
   - **Resolved**: 79 structured files (84%) are parsed directly in Python code (SQL, JSON, LOG, TXT). Only 15 files (16%) require multimodal VLM/LLM extraction (PNG, PDF).
5. **How is the final submission scored?**
   - **Resolved**: Case-level status accuracy, step-level accuracy, sequence accuracy, citation validity, and submission deliverables (`output.csv`, `evaluation/evaluation_report.md`, `evaluation/usage_report.md`, `code.zip`).
6. **Are there any remaining ambiguities before pipeline coding?**
   - **Resolved**: None. All schemas, rules, operations, ordering constraints, and file structures are verified against the real dataset.
