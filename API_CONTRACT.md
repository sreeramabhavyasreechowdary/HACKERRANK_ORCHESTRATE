# API_CONTRACT.md

Source of truth shared by backend and frontend.
Adjust field names to match SPEC_NOTES.md once the real output.csv schema is known.
If either side needs to deviate, change this file first, then both sides.

## Types

```
Run: {
  run_id: string,
  mode: "sample" | "final",
  status: "queued" | "running" | "done" | "failed",
  progress: { done: int, total: int },
  cost_usd: number,
  models: [{ name, input_tokens, output_tokens, calls, cost_usd }],
  validation: [{ check: string, passed: boolean, detail: string }]
}

CaseRow: {
  case_id: string,
  verdict: string,
  rules_fired: [string],
  match: true | false | null        // null in final mode
}

CaseTrace: {
  case_id: string,
  request: object,
  evidence: [{ evidence_id, media_type, url }],
  observations: [{
    evidence_id, location,
    data_present: true | false | "unknown",
    literal_description
  }],
  location_states: [{
    location,
    status: "deleted" | "present" | "unknown" | "conflicting",
    evidence_ids: [string]
  }],
  rules_fired: [{ rule_id, description, effect }],
  verdict: string,
  reason: string,
  citations: [evidence_id],
  reference_verdict: string | null  // sample mode only, supplied by the evaluator
}

Metrics: {
  accuracy: number,
  per_class: [{ label, precision, recall, f1, support }],
  confusion_matrix: { labels: [string], matrix: [[int]] },
  failures: [{ category, count, case_ids: [string] }],
  tune_score: number,
  holdout_score: number
}
```

## Endpoints (JSON, base path /api)

| Method | Path | Returns |
|---|---|---|
| POST | /runs  body: `{ "mode": "sample" \| "final" }` | Run |
| GET | /runs | Run[] |
| GET | /runs/{id} | Run |
| GET | /runs/{id}/cases | CaseRow[] |
| GET | /runs/{id}/cases/{case_id} | CaseTrace |
| GET | /runs/{id}/metrics | Metrics (404 in final mode) |
| GET | /runs/{id}/output.csv | file download |
| GET | /evidence/{evidence_id} | raw evidence file |

## Errors

All errors return `{ "error": string, "detail"?: string }` with a proper HTTP status.

## Rules

- `reference_verdict` and `match` must come only from the evaluator, never from the prediction path.
- `/evidence/{evidence_id}` must block path traversal and serve only indexed evidence files.
- The final-mode download is allowed only when every item in `validation` has `passed: true`.
