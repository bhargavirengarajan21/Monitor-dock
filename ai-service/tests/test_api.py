"""Story 1 — the HTTP routing layer dispatches to the backend."""

import pytest

from incident_backend.api import ApiError, dispatch
from incident_backend.backend import IncidentBackend
from incident_backend.connectors import InMemoryConnector
from incident_backend.models import Incident
from incident_memory_ai.config import load_config
from incident_memory_ai.meta_client import MetaModelClient


def _backend():
    def transport(url, headers, body):
        return {"choices": [{"message": {"content": "answer [1] [2]"}}]}

    config = load_config({"NO_MATCH_THRESHOLD": "0.55"})
    meta_client = MetaModelClient(config=config, transport=transport)
    connector = InMemoryConnector()
    connector.set_errors("payment-service", [{"count": 12, "url": "https://nr/err/1"}])
    return IncidentBackend(config=config, meta_client=meta_client, connector=connector)


def test_health():
    status, body = dispatch(_backend(), "GET", "/health", {})
    assert status == 200
    assert body == {"status": "ok"}


def test_approve_then_webhook_returns_an_answer():
    backend = _backend()
    incident = backend.add_incident(
        Incident(
            team_id="payments",
            title="Payment 409",
            error_codes=["ERR_PAYMENT_409"],
            cause="idempotency",
            fix="revert",
            url="https://notion/1",
        )
    )

    status, body = dispatch(
        backend, "POST", f"/postmortems/{incident.id}/approve", {}
    )
    assert status == 200
    assert body["published"] is True

    status, body = dispatch(
        backend,
        "POST",
        "/webhooks/alert?source=new_relic&team=payments",
        {"payload": {
            "details": {"error_code": "ERR_PAYMENT_409"},
            "targets": [{"labels": {"service": "payment-service"}}],
            "current_state": "open",
        }},
    )
    assert status == 200
    assert body["answer"]["no_match"] is False


def test_ask_refuses_action_requests():
    status, body = dispatch(
        _backend(),
        "POST",
        "/ask",
        {"question": "revert the deploy", "team_id": "payments"},
    )
    assert status == 200
    assert "refusal" in body
    assert "read-only" in body["refusal"]["message"].lower()


def test_webhook_requires_source_and_team():
    with pytest.raises(ApiError) as exc:
        dispatch(_backend(), "POST", "/webhooks/alert", {"payload": {}})
    assert exc.value.status == 400


def test_unknown_route_404s():
    with pytest.raises(ApiError) as exc:
        dispatch(_backend(), "GET", "/nope", {})
    assert exc.value.status == 404


def _draft_body():
    return {
        "team_id": "payments",
        "title": "Payment 409",
        "error_codes": ["ERR_PAYMENT_409"],
        "cause": "idempotency",
        "fix": "revert",
        "url": "https://notion/1",
    }


def test_create_list_and_get_incident_over_http():
    backend = _backend()

    status, created = dispatch(backend, "POST", "/incidents", _draft_body())
    assert status == 201
    assert created["status"] == "draft"
    incident_id = created["id"]

    status, listed = dispatch(backend, "GET", "/incidents?status=draft", {})
    assert status == 200
    assert [i["id"] for i in listed["incidents"]] == [incident_id]

    status, fetched = dispatch(backend, "GET", f"/incidents/{incident_id}", {})
    assert status == 200
    assert fetched["title"] == "Payment 409"


def test_create_requires_team_and_title():
    with pytest.raises(ApiError) as exc:
        dispatch(_backend(), "POST", "/incidents", {"title": "no team"})
    assert exc.value.status == 400


def test_get_missing_incident_404s():
    with pytest.raises(ApiError) as exc:
        dispatch(_backend(), "GET", "/incidents/does-not-exist", {})
    assert exc.value.status == 404


def test_reject_drops_a_draft():
    backend = _backend()
    _, created = dispatch(backend, "POST", "/incidents", _draft_body())

    status, body = dispatch(
        backend, "POST", f"/postmortems/{created['id']}/reject", {}
    )
    assert status == 200
    assert body["status"] == "rejected"

    _, fetched = dispatch(backend, "GET", f"/incidents/{created['id']}", {})
    assert fetched["status"] == "rejected"


def test_full_http_loop_create_approve_webhook_get_answer():
    backend = _backend()

    _, created = dispatch(backend, "POST", "/incidents", _draft_body())
    dispatch(backend, "POST", f"/postmortems/{created['id']}/approve", {})

    _, webhook = dispatch(
        backend,
        "POST",
        "/webhooks/alert?source=new_relic&team=payments",
        {"payload": {
            "details": {"error_code": "ERR_PAYMENT_409"},
            "targets": [{"labels": {"service": "payment-service"}}],
            "current_state": "open",
        }},
    )
    alert_id = webhook["alert"]["id"]
    assert webhook["answer"]["no_match"] is False

    # The saved answer is re-loadable for the answer screen (Story 24).
    status, answer = dispatch(backend, "GET", f"/answers/{alert_id}", {})
    assert status == 200
    assert answer["text"] == webhook["answer"]["text"]


def test_missing_answer_404s():
    with pytest.raises(ApiError) as exc:
        dispatch(_backend(), "GET", "/answers/nope", {})
    assert exc.value.status == 404


def test_recall_returns_facts_with_scores_for_the_ui():
    backend = _backend()
    _, created = dispatch(backend, "POST", "/incidents", _draft_body())
    dispatch(backend, "POST", f"/postmortems/{created['id']}/approve", {})

    _, webhook = dispatch(
        backend,
        "POST",
        "/webhooks/alert?source=new_relic&team=payments",
        {"payload": {
            "details": {"error_code": "ERR_PAYMENT_409"},
            "targets": [{"labels": {"service": "payment-service"}}],
            "current_state": "open",
        }},
    )
    # Facts-first payload for the UI (Stories 38, 39).
    assert webhook["matches"]
    assert 0.0 <= webhook["matches"][0]["score"] <= 1.0
    assert webhook["live_status"]["error_code"] == "ERR_PAYMENT_409"


def test_index_html_is_served():
    from incident_backend.api import _static_file

    served = _static_file("/")
    assert served is not None
    content_type, data = served
    assert content_type == "text/html"
    assert b"Incident Memory" in data
