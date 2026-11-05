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

## Backend (recall + capture paths)

The `incident_backend/` package wires the AI layer above into the full recall and
capture flow. Like the AI layer it is pure standard library — the Kafka broker,
Postgres and HTTP framework from the root README are modelled in process so the
whole flow runs and is tested offline.

| Story | File | What it does |
|---|---|---|
| **1** — Scaffold the backend | `incident_backend/api.py` | `http.server` HTTP layer; `dispatch()` is a pure router so routes are unit-tested without a socket. Run with `python -m incident_backend`. |
| **16** — Incidents and chunks tables | `incident_backend/models.py`, `store.py` | Dataclass models and an in-memory store for the `incidents` and `chunks` tables plus saved answers. |
| **20** — Permission filter by team | `incident_backend/permissions.py` | Restricts retrieval to a team's allowed `team_id`s *before* ranking; another team's postmortem is never returned. |
| **21** — Hybrid search | `incident_backend/search.py` | Keyword + vector (cosine) rankings merged with reciprocal rank fusion; an exact error-code query ranks its incident first. |
| **22** — No-match threshold | reused `answer.py` via `recall.py` | Below `NO_MATCH_THRESHOLD` the answer is "No similar incident found" with no model call. |
| **15** — Publish `postmortem.approved` | `incident_backend/events.py`, `capture.py` | In-process event bus with idempotent publish by `incidentId`; approving twice emits one event. |
| **17 / 18** — Index on events | `incident_backend/indexer.py` | Chunks, embeds and writes with `team_id`; reprocessing is safe; `document.changed` replaces only one section. |
| **9 / 31 / 33** — Normalize webhooks | `incident_backend/alerts.py` | New Relic and Prometheus Alertmanager webhooks map into one `Alert` (source, service, error code, open/close time, link). |
| **29** — Connector contract | `incident_backend/connectors.py` | One `Connector` protocol (`get_alert`, `get_errors`, `get_error_rate`); a new tool drops in without touching recall or capture. |
| **34** — New Relic connector | `incident_backend/newrelic_connector.py` | Real NerdGraph/NRQL connector; used automatically when `NEW_RELIC_API_KEY` + `NEW_RELIC_ACCOUNT_ID` are set, else the offline stub. Degrades to empty results with no key. |
| **19** — Alert starts recall | `incident_backend/recall.py`, `backend.py` | Webhook → permission filter → hybrid search → threshold → cited answer, saved against the alert. |

### Run the backend

```bash
cd ai-service
python -m incident_backend          # serves on :8000 (set PORT to override)

# alert webhook -> cited answer
curl -X POST "http://localhost:8000/webhooks/alert?source=new_relic&team=payments" \
  -H 'Content-Type: application/json' \
  -d '{"payload": {"details": {"error_code": "ERR_PAYMENT_409"},
       "targets": [{"labels": {"service": "payment-service"}}],
       "current_state": "open"}}'
```

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
