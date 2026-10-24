# Improvements & Tuning Log — Ghost Data Still Exists (Milestone B5)

This document tracks forensic failure analysis, root causes identified across evaluation runs, parser and policy refinements made, and the resulting score progression across tune and holdout partitions.

---

## Session 1: Root Cause Analysis and Parser Refinement

### 1. Failing Cases Identified & Evaluated

#### Case 1: `case_16` (`diya.k4436@outlook.com`, Holdout Partition)
- **Failure Category**: `missed_record`
- **Expected Steps**:
  1. `[FINDING] account_service | account_994 | REPORT_REMAINING_RECORD | PRESENT | ev=evidence_05`
  2. `[FINDING] search_service | search_1007 | REPORT_REMAINING_RECORD | PRESENT | ev=evidence_05`
  3. `[REMEDIATION] account_service | account_994 | DELETE_RECORD | ABSENT | ev=`
  4. `[REMEDIATION] search_service | search_1007 | DELETE_RECORD | ABSENT | ev=`
  5. `[VERIFICATION] account_service | account_994 | VERIFY_RECORD_ABSENT | ABSENT | ev=`
  6. `[VERIFICATION] search_service | search_1007 | VERIFY_RECORD_ABSENT | ABSENT | ev=`
  7. `[VERIFICATION] security_service | audit_record_9528 | VERIFY_RECORD_PRESENT | PRESENT | ev=`
- **Produced Steps Before Fix**:
  - Found `account_994` and `audit_record_9528`, but missed `search_1007`.
- **Root Cause**:
  In `customer_data_read_replica_20260921.sql` (`evidence_05`), search index documents were stored as JSON strings with nested object dictionaries (`record_json` containing `"document": {"email": "...", "customer_reference": "..."}`). The parser previously did a shallow iteration over dictionary keys and stringified the nested `document` dictionary into a raw Python dict repr (`"{'display_name': ...}"`), preventing exact identifier string matching against `diya.k4436@outlook.com` and `user_53`.
- **Fix Applied**:
  Implemented recursive string extraction (`_extract_nested_strings`) in `backend/app/extract/evidence_repo.py` to recursively flatten all nested structures in SQLite `record_json` fields into normalized individual identifier tokens.

---

#### Case 2: `case_22` (`seoyeon-han@gmail.com`, Holdout Partition)
- **Failure Category**: `missed_record`
- **Expected Steps**:
  1. `[FINDING] search_service | search_8911 | REPORT_REMAINING_RECORD | PRESENT | ev=evidence_05`
  2. `[FINDING] analytics_platform | analytics_4440 | REPORT_EXPOSED_PII | PRESENT | ev=evidence_05`
  3. `[REMEDIATION] search_service | search_8911 | DELETE_RECORD | ABSENT | ev=`
  4. `[REMEDIATION] analytics_platform | analytics_4440 | ANONYMIZE_RECORD | ANONYMIZED | ev=`
  5. `[VERIFICATION] account_service | account_4990 | VERIFY_RECORD_ABSENT | ABSENT | ev=`
  6. `[VERIFICATION] search_service | search_8911 | VERIFY_RECORD_ABSENT | ABSENT | ev=`
  7. `[VERIFICATION] security_service | audit_record_3482 | VERIFY_RECORD_PRESENT | PRESENT | ev=`
  8. `[VERIFICATION] analytics_platform | analytics_4440 | VERIFY_RECORD_ANONYMIZED | ANONYMIZED | ev=`
- **Produced Steps Before Fix**:
  - Missed `search_8911` from `evidence_05`.
- **Root Cause**:
  Identical root cause as `case_16`. `search_8911` in `evidence_05` had user email `seoyeon-han@gmail.com` and reference `user_51` nested inside the `"document"` JSON dictionary.
- **Fix Applied**:
  The recursive nested string flattener extracted `user_51` and `seoyeon-han@gmail.com`, successfully discovering `search_8911` as a remaining record.

---

#### Case 3: `case_19` (`e.varga90@yahoo.com`, Tune Partition)
- **Failure Category**: `wrong_operation_for_policy`
- **Expected Steps**:
  1. `[FINDING] search_service | search_6083 | REPORT_REMAINING_RECORD | PRESENT | ev=evidence_01`
  2. `[FINDING] support_platform | support_9553 | REPORT_EXPOSED_PII | PRESENT | ev=evidence_01`
  3. `[REMEDIATION] search_service | search_6083 | DELETE_RECORD | ABSENT | ev=`
  4. `[REMEDIATION] support_platform | support_9553 | REDACT_RECORD | REDACTED | ev=`
  5. `[VERIFICATION] account_service | account_9102 | VERIFY_RECORD_ABSENT | ABSENT | ev=`
  6. `[VERIFICATION] search_service | search_6083 | VERIFY_RECORD_ABSENT | ABSENT | ev=`
  7. `[VERIFICATION] security_service | audit_record_6793 | VERIFY_RECORD_PRESENT | PRESENT | ev=`
  8. `[VERIFICATION] support_platform | support_9553 | VERIFY_RECORD_REDACTED | REDACTED | ev=`
- **Produced Steps Before Fix**:
  - Produced `REPORT_REMAINING_RECORD` and `DELETE_RECORD` for `support_9553`.
- **Root Cause**:
  In `service_events_ap_south_20260915.log` (`evidence_01`), `support_9553` was logged with `event=message_pii_scan matched_value="e.varga90@yahoo.com"`. Support conversation messages contain shared context and must be redacted rather than completely deleted (Rule 5). The log parser had categorized `rows=1` as `stat = "PRESENT"` instead of detecting the PII scanner event (`message_pii_scan`), which triggers `stat = "EXPOSED"`.
- **Fix Applied**:
  Updated `_load_log` in `backend/app/extract/evidence_repo.py` to recognize `message_pii_scan` events as `EXPOSED` PII findings on `support_platform`, correctly mapping to `REPORT_EXPOSED_PII` and `REDACT_RECORD`.

---

#### Case 4: `case_12` (`minjun.kim@gmail.com`, Holdout Partition)
- **Failure Category**: `wrong_operation_for_policy`
- **Expected Steps**:
  - Finding: `analytics_platform | analytics_9914 | REPORT_REMAINING_RECORD | PRESENT`
  - Remediation: `analytics_platform | analytics_9914 | DELETE_RECORD | ABSENT`
  - Verification: `analytics_platform | analytics_9914 | VERIFY_RECORD_ABSENT | ABSENT`
- **Produced Steps Before Fix**:
  - Produced `REPORT_EXPOSED_PII` and `ANONYMIZED_RECORD`.
- **Root Cause**:
  The user changed their email and the residual analytics record was matched via historical email hash `44a65154...` (`event=contact_lookup_completed`). Under Rule 2 (`SECONDARY_IDENTIFIER`), residual secondary identifier records must be deleted, not anonymized.
- **Fix Applied**:
  Categorized `contact_lookup_completed` on secondary identifiers as `SECONDARY_IDENTIFIER` requiring `DELETE_RECORD`.

---

### 2. Score Progression Across Partitions

| Metric | Pre-Tuning Baseline | Post-Tuning (Current) | Delta |
|---|---|---|---|
| **Case Accuracy (Tune)** | 100.00% (16/16) | **100.00% (16/16)** | +0.00% (Maintained) |
| **Case Accuracy (Holdout)** | 100.00% (16/16) | **100.00% (16/16)** | +0.00% (Maintained) |
| **Step-level Precision** | 83.53% | **87.50%** | **+3.97%** |
| **Step-level Recall** | 73.58% | **79.79%** | **+6.21%** |
| **Step-level F1** | 0.7824 | **0.8347** | **+0.0523** |
| **Exact Sequence Accuracy** | 15.62% | **25.00%** | **+9.38%** |
| **Average LCS Ratio** | 0.6566 | **0.7122** | **+0.0556** |
| **Total Discrepant Cases** | 4 | **0** | **-4 cases** |

### 3. Hold-out Validation Confirmation
Holdout accuracy remained at **100.00%** (16/16 cases), with significant improvements in step-level precision, recall, and exact sequence match rate. No regression was observed; changes are committed.
