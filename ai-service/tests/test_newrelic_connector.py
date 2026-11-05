"""Story 34 — the New Relic connector implements the shared contract."""

import urllib.error

from incident_backend.newrelic_connector import NewRelicConnector


def _connector(results, capture=None):
    def transport(url, headers, body):
        if capture is not None:
            capture["url"] = url
            capture["headers"] = headers
            capture["body"] = body
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    return NewRelicConnector(api_key="NRAK-test", account_id="12345", transport=transport)


def test_get_errors_parses_nerdgraph_results():
    conn = _connector([
        {"error.message": "ERR_PAYMENT_409 Conflict", "count": 37},
        {"error.message": "ERR_PAYMENT_TIMEOUT", "count": 4},
    ])

    errors = conn.get_errors("payment-service", "1h")

    assert [e["message"] for e in errors] == ["ERR_PAYMENT_409 Conflict", "ERR_PAYMENT_TIMEOUT"]
    assert errors[0]["count"] == 37


def test_get_error_rate_returns_total_count():
    conn = _connector([{"count": 41}])
    assert conn.get_error_rate("payment-service", "30m") == 41.0


def test_sends_key_and_account_and_nrql():
    capture = {}
    conn = _connector([{"count": 1}], capture)

    conn.get_errors("payment-service", "2h")

    assert capture["headers"]["API-Key"] == "NRAK-test"
    body = capture["body"].decode("utf-8")
    assert "account(id: 12345)" in body
    assert "payment-service" in body
    assert "2 hours ago" in body  # window mapped into an NRQL SINCE clause


def test_unconfigured_connector_returns_empty_without_calling_out():
    calls = {"n": 0}

    def transport(url, headers, body):
        calls["n"] += 1
        return {}

    conn = NewRelicConnector(api_key="", account_id="", transport=transport)

    assert conn.configured is False
    assert conn.get_errors("payment-service", "1h") == []
    assert conn.get_error_rate("payment-service", "1h") == 0.0
    assert calls["n"] == 0  # no network attempt when there is no key


def test_network_error_degrades_to_empty():
    def transport(url, headers, body):
        raise urllib.error.URLError("offline")

    conn = NewRelicConnector(api_key="NRAK-test", account_id="12345", transport=transport)

    assert conn.get_errors("payment-service", "1h") == []
    assert conn.get_error_rate("payment-service", "1h") == 0.0
