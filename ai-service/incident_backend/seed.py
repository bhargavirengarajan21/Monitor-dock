"""Story 25 — load synthetic incidents and seeded fix PRs.

Reads the bundled ``demo_data/incidents.json`` (fabricated data — no real
incidents) and returns a fully populated :class:`IncidentBackend`: teams
registered, the permission policy built, the connector primed with live error
counts, and every demo incident created *and approved* so it is already indexed
and searchable.

In production the same seeding shape runs against real approved postmortems; the
only difference is where the incidents come from.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from incident_memory_ai.config import Config
from incident_memory_ai.meta_client import MetaModelClient

from .backend import IncidentBackend
from .connectors import InMemoryConnector
from .models import Incident
from .newrelic_connector import NewRelicConnector
from .registry import TeamRegistry

DEMO_DATA = Path(__file__).resolve().parent / "demo_data" / "incidents.json"


def load_dataset(path: Optional[Path] = None) -> dict:
    with open(path or DEMO_DATA, encoding="utf-8") as handle:
        return json.load(handle)


def build_registry(dataset: dict) -> TeamRegistry:
    registry = TeamRegistry()
    for team_id, info in dataset.get("teams", {}).items():
        registry.register(
            team_id, info.get("tool", "new_relic"), info.get("visible_teams", [])
        )
    return registry


def build_connector(dataset: dict):
    """Pick the live-status connector.

    Uses the real :class:`NewRelicConnector` when ``NEW_RELIC_API_KEY`` and
    ``NEW_RELIC_ACCOUNT_ID`` are set, otherwise the offline stub primed with the
    dataset's canned error counts so the demo shows live numbers with no account.
    """

    new_relic = NewRelicConnector()
    if new_relic.configured:
        return new_relic

    connector = InMemoryConnector(name="demo")
    for service, errors in dataset.get("live_errors", {}).items():
        connector.set_errors(service, errors)
    return connector


def seed_backend(
    dataset: Optional[dict] = None,
    config: Optional[Config] = None,
    meta_client: Optional[MetaModelClient] = None,
) -> IncidentBackend:
    """Return an :class:`IncidentBackend` populated from the demo dataset."""

    dataset = dataset or load_dataset()
    registry = build_registry(dataset)
    connector = build_connector(dataset)

    backend = IncidentBackend(
        config=config,
        meta_client=meta_client,
        connector=connector,
        permissions=registry.permission_policy(),
    )
    backend.registry = registry  # expose the registry for the API / UI

    for row in dataset.get("incidents", []):
        incident = backend.add_incident(
            Incident(
                team_id=row["team_id"],
                title=row["title"],
                error_codes=list(row.get("error_codes", [])),
                cause=row.get("cause", ""),
                fix=row.get("fix", ""),
                service=row.get("service", ""),
                url=row.get("url", ""),
            )
        )
        backend.approve(incident.id)  # approved -> indexed -> searchable

    return backend


def seed_enabled() -> bool:
    """True when the server should boot pre-seeded (SEED_DEMO=1)."""

    return os.environ.get("SEED_DEMO", "").strip().lower() in ("1", "true", "yes")
