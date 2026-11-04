# Incident Memory — AI layer

The Python services behind the recall and capture paths. Pure standard library
at runtime (uses `urllib`), so it runs offline and in CI with no third-party
install.

## Stories implemented

| Story | File | What it does |
|---|---|---|
| **3** — Meta Model API client for Muse Spark | `incident_memory_ai/meta_client.py` | Reads base URL, key, model ID from env vars; returns text and JSON responses. |
| **4** — Local embedding model through Ollama | `incident_memory_ai/embeddings.py` | `embed(text)` returns a 768-dim vector (matching the pgvector column); works offline via a deterministic fallback. |
| **12** — Muse Spark drafts a postmortem | `incident_memory_ai/postmortem.py` | Turns New Relic error + deploy + fix PR into structured JSON; retries invalid JSON once, then flags. |
| **23** — Cited answer with past fix + live status | `incident_memory_ai/answer.py` | Past cause/fix plus current error count; every claim links to a postmortem or monitoring error; optional suspect commits. |
| **40** — Read-only assistant refuses actions | `incident_memory_ai/guardrails.py` | Detects "revert the deploy" / "restart the service" and refuses with a read-only explanation plus runbook/PR links. |
| **26** — Eval script | `scripts/eval.py` | Prints hit rate @3, honest-miss rate, and p50/p95 latency. |

## Configuration

All configuration comes from environment variables (see the root README's
"Environment variables" section): `META_API_BASE_URL`, `MODEL_API_KEY`,
`META_CHAT_MODEL`, `META_TRANSCRIBE_MODEL`, `EMBEDDING_MODEL`, `OLLAMA_BASE_URL`,
`NO_MATCH_THRESHOLD`.

## Run the tests

```bash
cd ai-service
python -m pytest        # or: python -m unittest discover -s tests
```

## Run the eval

```bash
cd ai-service
python scripts/eval.py            # uses the bundled eval/alerts.json
python scripts/eval.py my.json    # or a custom dataset
```
