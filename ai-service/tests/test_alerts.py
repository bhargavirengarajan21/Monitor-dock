"""Stories 9, 31 & 33 — webhook normalization into one incident format."""

from incident_backend.alerts import NEW_RELIC, PROMETHEUS, normalize


def test_new_relic_webhook_is_normalized_with_code_service_and_timestamp():
    payload = {
        "condition_name": "ERR_PAYMENT_409",
        "details": {"error_code": "ERR_PAYMENT_409"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
        "timestamp": "2026-11-04T10:00:00Z",
        "incident_url": "https://nr/incident/1",
    }

    alert = normalize("new_relic", payload, team_id="payments")

    assert alert.source_tool == NEW_RELIC
    assert alert.error_code == "ERR_PAYMENT_409"
    assert alert.service == "payment-service"
    assert alert.opened_at == "2026-11-04T10:00:00Z"
    assert not alert.is_closed


def test_closed_new_relic_alert_carries_a_close_time():
    payload = {
        "condition_name": "ERR_PAYMENT_409",
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "closed",
        "timestamp": "2026-11-04T10:30:00Z",
    }

    alert = normalize("new_relic", payload, team_id="payments")

    assert alert.is_closed
    assert alert.closed_at == "2026-11-04T10:30:00Z"


def test_prometheus_and_new_relic_produce_the_same_shape():
    prom = normalize(
        "prometheus",
        {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"service": "payment-service", "error_code": "ERR_PAYMENT_409"},
                    "startsAt": "2026-11-04T10:00:00Z",
                    "generatorURL": "https://prom/graph",
                }
            ],
        },
        team_id="payments",
    )

    assert prom.source_tool == PROMETHEUS
    assert prom.service == "payment-service"
    assert prom.error_code == "ERR_PAYMENT_409"
    # Same fields a New Relic alert fills, so recall treats both identically.
    assert set(prom.to_dict()) == {
        "id", "source_tool", "service", "error_code", "team_id",
        "opened_at", "closed_at", "url", "is_closed",
    }


def test_unknown_source_tool_is_rejected():
    try:
        normalize("datadog", {}, team_id="payments")
    except ValueError as exc:
        assert "datadog" in str(exc)
    else:  # pragma: no cover - the call above must raise
        raise AssertionError("expected ValueError for an unregistered tool")
