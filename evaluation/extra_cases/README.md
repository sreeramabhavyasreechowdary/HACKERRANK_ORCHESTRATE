# Extra Evaluation Cases

This directory contains synthetic evaluation cases designed to test critical edge cases identified in the challenge requirements:

| Case ID | Scenario Description | Key Risk / Edge Case Tested | Expected Status | Step Count |
|---|---|---|---|---|
| `case_extra_01` | Historical Identity Resolution | User changed email prior to deletion request. Search index still holds a record under the old email. Tests historical identifier expansion via `user_audit_log.csv`. | `INCOMPLETE` | 4 steps |
| `case_extra_02` | Account Tombstone Leftover PII | Primary account deleted, but account tombstone in `identity_service` still retains `email_hash` (violating Rule 15, which permits only stable `user_id`). | `INCOMPLETE` | 4 steps |
| `case_extra_03` | Active Sync Recreation Risk | Active data flow job in `integration_service` synchronizes external CRM records, creating risk of recreating deleted user data. Tests detection of `REPORT_ACTIVE_DATA_FLOW` and remediation `DISABLE_DATA_FLOW`. | `INCOMPLETE` | 4 steps |
| `case_extra_04` | Non-Deletion User Request | User submitted request for data export / invoice inquiry with explicit note not to delete account. Tests `NOT_APPLICABLE` classification with empty `steps_json` (`[]`). | `NOT_APPLICABLE` | 0 steps |
