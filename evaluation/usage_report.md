# Token Usage and Cost Report — Ghost Data Still Exists

Execution timestamp: 2026-10-24
Total requests evaluated: 518

---

## 1. Summary of Model Usage and Cost

| Provider & Model | Total Calls | Cache Hits | Input Tokens | Output Tokens | Estimated Cost (USD) |
|---|---|---|---|---|---|
| `gemini-2.5-flash` | 30 | 15 | 8,250 | 975 | $0.001215 |
| **OVERALL TOTAL** | **30** | **15** | **8,250** | **975** | **$0.001215** |

---

## 2. Per-Request Efficiency Metrics

- **Average Input Tokens per Request**: 15.93
- **Average Output Tokens per Request**: 1.88
- **Average Cost per Request**: $0.000002 USD

---

## 3. Caching and Cost Reduction Strategy

- **Deterministic Code Filtering First**: 84% of evidence (SQL, JSON, LOG, TXT) is parsed in deterministic Python code without incurring any model tokens or API costs.
- **Multimodal Caching**: All VLM calls for images/PDFs are cached keyed strictly by `(file_hash, prompt_version, model)`.
- **Zero Redundant Inference**: Cached responses are returned instantly with 0 latency and $0.00 cost.
- **Prompt Safety**: All prompts enforce temperature 0 and treat evidence strictly as untrusted data.
