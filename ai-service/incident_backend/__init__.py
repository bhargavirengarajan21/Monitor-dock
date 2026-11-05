"""Incident Memory backend.

The recall and capture paths wired on top of the AI layer: a webhook-driven
alert ingest, a team permission filter, hybrid (keyword + vector) search merged
with reciprocal rank fusion, a no-match threshold, an in-process event bus
standing in for Kafka, an indexer, and the human-approval capture flow.

Pure standard library at runtime, like the AI layer, so it runs offline and in
CI with nothing to install.
"""

from .backend import IncidentBackend
from .capture import CaptureService
from .connectors import Connector, InMemoryConnector
from .newrelic_connector import NewRelicConnector
from .events import DOCUMENT_CHANGED, POSTMORTEM_APPROVED, EventBus
from .indexer import Indexer
from .models import Alert, Chunk, Incident
from .permissions import PermissionPolicy
from .recall import RecallService
from .search import HybridSearch, SearchHit
from .store import InMemoryStore

__all__ = [
    "IncidentBackend",
    "CaptureService",
    "Connector",
    "InMemoryConnector",
    "NewRelicConnector",
    "EventBus",
    "POSTMORTEM_APPROVED",
    "DOCUMENT_CHANGED",
    "Indexer",
    "Alert",
    "Chunk",
    "Incident",
    "PermissionPolicy",
    "RecallService",
    "HybridSearch",
    "SearchHit",
    "InMemoryStore",
]
