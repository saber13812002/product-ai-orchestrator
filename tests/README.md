# Tests

The project's test suites live in [`workflow/tests/`](../workflow/tests/) so they import the
`workflow` package directly. They are **hermetic** — a fake router stands in for the LLM, so they
never call a real model and need no network or `.env`.

Suites:

| Suite | Covers |
|---|---|
| `test_router.py` | role→model resolution + honest token ledger |
| `test_state.py` | state persistence |
| `test_smoke.py` | Manager → Product Analyst → persist |
| `test_full_pipeline.py` | the full 13-step pipeline + quality loop |
| `test_robustness.py` | truncation / JSON-repair edge cases |
| `test_enrichment.py` | the 8 enrichment agents + document bundle + completeness gate |

Run them inside the container (the Python deps are installed there):

```bash
for t in test_router test_state test_smoke test_full_pipeline test_robustness test_enrichment; do
  docker compose exec agno-agentos uv run python -m workflow.tests.$t
done
```

Each prints `OK` on success and exits 0.
