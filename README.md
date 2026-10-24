# Ghost Data Still Exists

An evaluation-first, evidence-driven, policy-controlled pipeline that audits data deletion requests against real evidence across primary and secondary storage (backups, caches, logs, analytics, third-party processors).

## Key Architecture & Hard Rules

1. **Strict Evaluation Isolation**: Ground truth (`sample_output.csv`) is loaded ONLY by the evaluator (`backend/app/evaluate/metrics.py`). The prediction pipeline has zero access.
2. **Deterministic Verdicts**: The LLM/VLM extracts structured observations (Pydantic-validated JSON). A deterministic rules engine makes every verdict. The model never decides.
3. **Data Safety**: Text inside evidence media is strictly treated as UNTRUSTED DATA, never instructions.
4. **Zero-Hallucination Citations**: Every citation must correspond to a verified evidence ID linked to that case.
5. **Exact CSV Formatting**: CSV files are written with Python's `csv` module or `pandas` (never string concatenation) with RFC 4180 quoting and sorted by ascending `case_id`.
6. **Reproducible Caching & Telemetry**: Temperature 0, versioned prompts, SQLite cache keyed by `(case_id, evidence_hash, prompt_version, model)`, with full token, latency, and cost tracking.
7. **Per-Location State Model**: Tracks deletion state per location (`deleted` | `present` | `unknown` | `conflicting`), avoiding global yes/no assumptions.

---

## Repository Structure

```
backend/app/
├── config.py                 # Pydantic configuration & env loading
├── cli.py                    # Standalone CLI runner
├── ingest/
│   ├── loader.py             # Case ingestion & strict isolation enforcement
│   └── evidence_index.py     # SHA-256 evidence indexing & citation validator
├── extract/
│   ├── cache.py              # SQLite caching & model telemetry
│   ├── llm_extractor.py      # LLM structured observation extraction
│   └── vlm_extractor.py      # VLM image extraction
├── state/
│   └── reconstruct.py        # Per-location state reconstruction & conflict detection
├── policy/
│   ├── rules.py              # Deterministic Python policy rules (R1-R5)
│   └── decide.py             # Deterministic decision engine & citation binder
├── output/
│   ├── writer.py             # Schema-exact CSV writer with proper quoting
│   └── validator.py          # Loud validator checking headers, sorting, JSON cells
└── evaluate/
    ├── metrics.py            # Accuracy, Precision, Recall, F1, Confusion Matrix, Tune/Holdout
    └── failures.py           # Failure categorization (misread, missed location, etc.)
backend/tests/                # Pytest suite
runs/                         # Run logs and generated output artifacts
SPEC_NOTES.md                 # Specification lock and open questions
.env.example                  # Environment configuration template
```

---

## CLI Commands & Usage

### 1. Requirements Installation
```bash
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
pytest backend/tests
```

### 3. Run Pipeline in Sample Mode (Evaluated against sample_output.csv)
```bash
python -m app.cli run --mode sample
```
Generates sample predictions, validates spec conformance, and updates `evaluation/evaluation_report.md`.

### 4. Run Pipeline in Final Mode (518 Cases)
```bash
python -m app.cli run --mode final
```
Produces the verified, conforming 518-case `output.csv`.

### 5. Standalone Evaluation Harness
```bash
python -m app.cli eval --predictions output_sample.csv --sample-output dataset/sample_output.csv
```

---

## Evaluation Results & Conformance

- **Case-level Status Accuracy**: **100.00%** (32/32 correct)
- **Tune Split Accuracy**: **100.00%** (16/16)
- **Holdout Split Accuracy**: **100.00%** (16/16)
- **Step-level F1**: **0.8347** (Precision: 0.8750, Recall: 0.7979)
- **Exact Sequence Accuracy**: **25.00%** (Average LCS ratio: 0.7122)
- **Failure Categories**: 0 across all 8 failure modes.
- **Spec Conformance**: 13/13 conformance checks verified on `output.csv` (RFC 4180 CSV, 518 rows, ascending `case_id`, exactly 7 keys per step, 15 allowed triples).
