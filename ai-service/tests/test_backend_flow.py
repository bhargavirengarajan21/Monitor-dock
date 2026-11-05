"""Stories 19 & 22 end to end, plus the capture flow (Stories 15, 17).

Drives the wired :class:`IncidentBackend` the way the HTTP layer does: approve a
postmortem, then fire an alert and get a saved, cited answer — or an honest
no-match when nothing is similar.
"""

from incident_backend.backend import IncidentBackend
from incident_backend.connectors import InMemoryConnector
from incident_backend.models import Incident
from incident_memory_ai.config import load_config
from incident_memory_ai.meta_client import MetaModelClient


def _backend():
    # Offline Meta client: a fixed reply, so no network and deterministic text.
    def transport(url, headers, body):
        return {"choices": [{"message": {"content": "Past fix [1]; 37 errors now [2]."}}]}

    config = load_config({"NO_MATCH_THRESHOLD": "0.55"})
    meta_client = MetaModelClient(config=config, transport=transport)
    connector = InMemoryConnector()
    connector.set_errors(
        "payment-service",
        [{"message": "409", "trace": "", "count": 37, "url": "https://nr/err/1"}],
    )
    return IncidentBackend(config=config, meta_client=meta_client, connector=connector)


def _approved_incident(backend: IncidentBackend) -> Incident:
    incident = backend.add_incident(
        Incident(
            team_id="payments",
            title="Payment 409 after idempotency change",
            error_codes=["ERR_PAYMENT_409"],
            cause="Deploy abc123 made the idempotency key non-unique.",
            fix="Reverted the key change in PR #42.",
            url="https://notion/incident-01",
        )
    )
    backend.approve(incident.id)  # publishes the event; indexer makes it searchable
    return incident


def test_alert_triggers_recall_and_saves_a_cited_answer():
    backend = _backend()
    _approved_incident(backend)

    payload = {
        "condition_name": "ERR_PAYMENT_409",
        "details": {"error_code": "ERR_PAYMENT_409"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
        "timestamp": "2026-11-04T10:00:00Z",
        "incident_url": "https://nr/incident/1",
    }
    result = backend.ingest_alert("new_relic", payload, team_id="payments")

    answer = result["answer"]
    assert answer["no_match"] is False
    kinds = [c["kind"] for c in answer["citations"]]
    assert "postmortem" in kinds and "monitoring" in kinds
    # The answer was saved against the alert for the UI (Story 19).
    assert backend.saved_answer(result["alert"]["id"])["text"] == answer["text"]


def test_unknown_alert_is_an_honest_no_match():
    backend = _backend()
    _approved_incident(backend)

    payload = {
        "condition_name": "ERR_NEVER_SEEN_777",
        "details": {"error_code": "ERR_NEVER_SEEN_777"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
    }
    result = backend.ingest_alert("new_relic", payload, team_id="payments")

    assert result["answer"]["no_match"] is True
    assert result["answer"]["text"] == "No similar incident found"


def test_draft_is_not_searchable_until_approved():
    backend = _backend()
    backend.add_incident(
        Incident(
            team_id="payments",
            title="Payment 409 after idempotency change",
            error_codes=["ERR_PAYMENT_409"],
            cause="Idempotency key non-unique.",
            fix="Reverted in PR #42.",
            url="https://notion/incident-01",
        )
    )
    # No approval yet, so nothing was indexed.
    payload = {
        "details": {"error_code": "ERR_PAYMENT_409"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
    }
    result = backend.ingest_alert("new_relic", payload, team_id="payments")
    assert result["answer"]["no_match"] is True


def test_approving_twice_indexes_once():
    backend = _backend()
    incident = _approved_incident(backend)
    chunks_after_first = len(backend.store.all_chunks())

    published_again = backend.approve(incident.id)

    assert published_again is False  # idempotent (Story 15)
    assert len(backend.store.all_chunks()) == chunks_after_first
