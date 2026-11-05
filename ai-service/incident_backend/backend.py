"""The wired backend facade.

Assembles the store, event bus, indexer, hybrid search, connectors and the
recall and capture services into one object the HTTP layer (Story 1) and the
tests drive. Everything is injectable so a test can pass a stub Meta Model
client, a canned connector, or a custom permission policy; nothing here reaches
the network by default.
"""

from __future__ import annotations

from typing import Optional

from incident_memory_ai.answer import AnswerBuilder
from incident_memory_ai.config import Config, load_config
from incident_memory_ai.embeddings import Embedder
from incident_memory_ai.meta_client import MetaModelClient

from . import alerts as alert_normalizer
from .capture import CaptureService
from .connectors import Connector, InMemoryConnector
from .events import EventBus
from .indexer import Indexer
from .models import Alert, Incident
from .permissions import PermissionPolicy
from .recall import RecallService
from .search import HybridSearch
from .store import InMemoryStore


class IncidentBackend:
    """Everything the recall and capture paths need, wired together."""

    def __init__(
        self,
        config: Optional[Config] = None,
        meta_client: Optional[MetaModelClient] = None,
        embedder: Optional[Embedder] = None,
        connector: Optional[Connector] = None,
        permissions: Optional[PermissionPolicy] = None,
    ) -> None:
        self.config = config or load_config()
        self.meta_client = meta_client or MetaModelClient(config=self.config)
        self.embedder = embedder or Embedder(config=self.config)
        self.connector = connector or InMemoryConnector()
        self.permissions = permissions or PermissionPolicy()

        # Set by the seeder when the backend is booted with a team registry.
        self.registry = None

        self.store = InMemoryStore()
        self.bus = EventBus()

        self.indexer = Indexer(self.store, self.embedder)
        self.indexer.subscribe(self.bus)

        self.search = HybridSearch(self.store, self.embedder, self.permissions)
        self.answer_builder = AnswerBuilder(
            self.meta_client, no_match_threshold=self.config.no_match_threshold
        )
        self.recall = RecallService(
            self.store, self.search, self.answer_builder, self.connector
        )
        self.capture = CaptureService(self.store, self.bus)

    # --- capture path --------------------------------------------------------
    def add_incident(self, incident: Incident) -> Incident:
        """Store a draft incident (from the capture/postmortem pipeline)."""

        return self.store.save_incident(incident)

    def create_incident(self, data: dict) -> Incident:
        """Build and store a draft incident from a plain dict (HTTP body)."""

        incident = Incident(
            team_id=data["team_id"],
            title=data["title"],
            error_codes=list(data.get("error_codes", [])),
            cause=data.get("cause", ""),
            fix=data.get("fix", ""),
            postmortem=data.get("postmortem", ""),
            source_tool=data.get("source_tool", ""),
            service=data.get("service", ""),
            call_url=data.get("call_url", ""),
            url=data.get("url", ""),
        )
        return self.store.save_incident(incident)

    def list_incidents(self, status: Optional[str] = None) -> list[dict]:
        """List incidents, optionally filtered by status (for the approve screen)."""

        incidents = self.store.incidents()
        if status:
            incidents = [i for i in incidents if i.status == status]
        return [i.to_dict() for i in incidents]

    def get_incident(self, incident_id: str) -> Optional[dict]:
        """Fetch one incident to review (for the approve screen)."""

        incident = self.store.get_incident(incident_id)
        return incident.to_dict() if incident else None

    def approve(self, incident_id: str) -> bool:
        """Approve a draft; the indexer makes it searchable (Stories 15, 17)."""

        return self.capture.approve(incident_id)

    def reject(self, incident_id: str) -> None:
        """Reject a draft so it never becomes memory (the Reject button)."""

        self.capture.reject(incident_id)

    # --- recall path ---------------------------------------------------------
    def ingest_alert(self, source_tool: str, payload: dict, team_id: str) -> dict:
        """Normalize a webhook, run recall, and return the saved answer.

        This is the whole Story 19 flow: webhook in, cited answer out.
        """

        alert = alert_normalizer.normalize(source_tool, payload, team_id)
        result = self.recall.handle_alert(alert)
        return {"alert": alert.to_dict(), **result}

    def handle_alert(self, alert: Alert) -> dict:
        result = self.recall.handle_alert(alert)
        return {"alert": alert.to_dict(), **result}

    def ask(self, question: str, team_id: str, service: str = "", error_code: str = "") -> dict:
        """Answer a free-text question (Story 19 + the Story 40 guardrail)."""

        return self.recall.handle_question(question, team_id, service, error_code)

    def saved_answer(self, alert_id: str) -> Optional[dict]:
        return self.store.get_answer(alert_id)
