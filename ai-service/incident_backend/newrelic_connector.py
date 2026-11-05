"""Story 34 — New Relic connector.

Acceptance criteria: implements the connector contract (Story 29) against a free
New Relic account; returns real errors and error rate for the test service.

Speaks New Relic's NerdGraph GraphQL API, running NRQL to read errors. Like the
rest of the stack it uses only the standard library (urllib) and takes an
injectable ``transport`` so tests never hit the network. Credentials come from
``NEW_RELIC_API_KEY`` and ``NEW_RELIC_ACCOUNT_ID`` (env or constructor). With no
key, or when New Relic is unreachable, it degrades to empty results instead of
raising, so a demo without a New Relic account still runs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable, List, Optional

from .models import Alert

NERDGRAPH_URL = "https://api.newrelic.com/graphql"

# A transport takes (url, headers, body_bytes) and returns the decoded JSON.
Transport = Callable[[str, dict, bytes], dict]


def _urllib_transport(url: str, headers: dict, body: bytes, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # pragma: no cover - network path
        return json.loads(resp.read().decode("utf-8"))


def _window_to_since(window: str) -> str:
    """Turn a short window like ``1h`` or ``30m`` into an NRQL SINCE clause."""

    w = (window or "1h").strip().lower()
    units = {"h": "hours", "m": "minutes", "d": "days", "s": "seconds"}
    if w and w[-1] in units and w[:-1].isdigit():
        return f"{int(w[:-1])} {units[w[-1]]} ago"
    return "60 minutes ago"  # safe default


class NewRelicConnector:
    """Reads errors and error rate for a service from New Relic (Story 34)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        transport: Optional[Transport] = None,
        name: str = "new_relic",
    ) -> None:
        self.name = name
        self.api_key = api_key if api_key is not None else os.environ.get("NEW_RELIC_API_KEY", "")
        self.account_id = (
            account_id if account_id is not None else os.environ.get("NEW_RELIC_ACCOUNT_ID", "")
        )
        self._transport = transport or _urllib_transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.account_id)

    def _run_nrql(self, nrql: str) -> List[dict]:
        """Run an NRQL query and return its result rows (empty if unavailable)."""

        if not self.configured:
            return []
        query = (
            "{ actor { account(id: %s) { nrql(query: %s) { results } } } }"
            % (int(self.account_id), json.dumps(nrql))
        )
        headers = {"Content-Type": "application/json", "API-Key": self.api_key}
        body = json.dumps({"query": query}).encode("utf-8")
        try:
            response = self._transport(NERDGRAPH_URL, headers, body)
        except (urllib.error.URLError, OSError, ValueError):
            return []
        try:
            return response["data"]["actor"]["account"]["nrql"]["results"] or []
        except (KeyError, TypeError):
            return []

    # --- Connector contract --------------------------------------------------
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        # Alerts reach the backend via the webhook (Story 9); this connector is
        # used for live error context, so there is nothing to fetch by id here.
        return None

    def get_errors(self, service: str, window: str) -> List[dict]:
        """Recent errors for a service, as ``{message, count, url}`` rows."""

        since = _window_to_since(window)
        nrql = (
            "SELECT count(*) AS count FROM TransactionError "
            f"WHERE appName = '{service}' FACET error.message SINCE {since}"
        )
        errors: List[dict] = []
        for row in self._run_nrql(nrql):
            message = row.get("error.message") or (row.get("facet") or [""])[0]
            errors.append(
                {
                    "message": message,
                    "trace": "",
                    "count": int(row.get("count", 0)),
                    "url": "https://one.newrelic.com/errors-inbox",
                }
            )
        return errors

    def get_error_rate(self, service: str, window: str) -> float:
        """Total errors for the service over the window (errors per window)."""

        since = _window_to_since(window)
        nrql = (
            "SELECT count(*) AS count FROM TransactionError "
            f"WHERE appName = '{service}' SINCE {since}"
        )
        rows = self._run_nrql(nrql)
        if not rows:
            return 0.0
        return float(rows[0].get("count", 0))
