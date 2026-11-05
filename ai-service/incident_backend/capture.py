"""Story 15 — publish postmortem.approved to Kafka.

Acceptance criteria: approving sends one event keyed by incidentId; approving
twice does not create duplicate events.

A human approves every postmortem before it becomes memory (the README's
guarantee that an AI mistake never becomes team knowledge). Approval flips the
incident to ``approved`` and publishes one idempotent event; the indexer, a
subscriber, turns it into searchable chunks.
"""

from __future__ import annotations

from .events import POSTMORTEM_APPROVED, EventBus
from .models import APPROVED, REJECTED
from .store import InMemoryStore


class CaptureService:
    """Approves or rejects drafts and publishes approval events."""

    def __init__(self, store: InMemoryStore, bus: EventBus) -> None:
        self.store = store
        self.bus = bus

    def approve(self, incident_id: str) -> bool:
        """Approve a draft and publish its event; return True if newly published.

        Keyed by incident id, so approving twice publishes exactly one event
        (Story 15) and the indexer runs once.
        """

        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise KeyError(f"No incident {incident_id!r} to approve")
        incident.status = APPROVED
        self.store.save_incident(incident)
        return self.bus.publish(
            POSTMORTEM_APPROVED, key=incident_id, payload={"incident_id": incident_id}
        )

    def reject(self, incident_id: str) -> None:
        """Reject a draft; nothing is published, so it never becomes memory."""

        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise KeyError(f"No incident {incident_id!r} to reject")
        incident.status = REJECTED
        self.store.save_incident(incident)
