"""Stories 9, 31 & 33 — ingest and normalize monitoring webhooks.

Story 9 (New Relic alert webhook): a New Relic alert posts to the backend; the
payload is stored with error code, service and timestamp.

Story 31 (detect a resolved incident when the alert closes): the webhook also
fires on close; a closed alert carries its close time so capture can turn it into
a draft incident.

Story 33 (normalize alerts from any tool into one incident format): webhooks
from New Relic and Prometheus Alertmanager become the same :class:`Alert` record
— source tool, service, error code, open/close time and a link back.

Parsing is defensive: real webhook payloads vary, so each field falls back
gracefully rather than raising on a missing key.
"""

from __future__ import annotations

from typing import Optional

from .models import Alert

NEW_RELIC = "new_relic"
PROMETHEUS = "prometheus"


def _first(mapping: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return default


def normalize_new_relic(payload: dict, team_id: str) -> Alert:
    """Map a New Relic alert webhook into an :class:`Alert`."""

    details = payload.get("details") or {}
    labels = {}
    targets = payload.get("targets") or []
    if targets and isinstance(targets[0], dict):
        labels = targets[0].get("labels") or {}

    service = _first(labels, "service", "app", default=_first(details, "service"))
    error_code = _first(
        details,
        "error_code",
        "errorCode",
        default=_first(payload, "condition_name", "title"),
    )
    state = _first(payload, "current_state", "state", default="open").lower()
    opened_at = _first(payload, "opened_at", "timestamp") or None
    closed_at = None
    if state in ("closed", "resolved", "acknowledged_closed"):
        closed_at = _first(payload, "closed_at", "timestamp") or opened_at

    return Alert(
        source_tool=NEW_RELIC,
        service=service,
        error_code=error_code,
        team_id=team_id,
        opened_at=opened_at,
        closed_at=closed_at,
        url=_first(payload, "incident_url", "url"),
    )


def normalize_prometheus(payload: dict, team_id: str) -> Alert:
    """Map a Prometheus Alertmanager webhook into an :class:`Alert`."""

    alerts = payload.get("alerts") or []
    first = alerts[0] if alerts and isinstance(alerts[0], dict) else {}
    labels = first.get("labels") or {}
    annotations = first.get("annotations") or {}

    status = _first(first, "status", default=_first(payload, "status", default="firing"))
    starts_at = first.get("startsAt") or None
    ends_at = first.get("endsAt") or None
    # Alertmanager sends a zero timestamp for alerts that have not resolved.
    if status.lower() != "resolved" or (ends_at and ends_at.startswith("0001")):
        ends_at = None

    return Alert(
        source_tool=PROMETHEUS,
        service=_first(labels, "service", "job"),
        error_code=_first(labels, "error_code", "alertname", default=_first(annotations, "summary")),
        team_id=team_id,
        opened_at=starts_at,
        closed_at=ends_at,
        url=_first(first, "generatorURL", default=_first(payload, "externalURL")),
    )


def normalize(source_tool: str, payload: dict, team_id: str) -> Alert:
    """Dispatch to the right normalizer by source tool name (Story 33)."""

    tool = (source_tool or "").lower()
    if tool in (NEW_RELIC, "newrelic", "nr"):
        return normalize_new_relic(payload, team_id)
    if tool in (PROMETHEUS, "alertmanager"):
        return normalize_prometheus(payload, team_id)
    raise ValueError(f"No connector registered for source tool {source_tool!r}")
