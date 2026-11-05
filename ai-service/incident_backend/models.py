"""Backend domain models.

These mirror the simplified data model in the root README: an ``incidents``
table and a ``chunks`` table (Story 16 — database tables for incidents and
chunks), plus the normalized ``Alert`` record every monitoring connector maps
into (Story 33 — normalize alerts from any tool into one incident format).

The AI layer stays pure standard library; the backend keeps the same rule, so
these are plain dataclasses with ``to_dict`` for the HTTP layer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

# Lifecycle values for an incident, matching the README's ``status`` column.
DRAFT = "draft"
APPROVED = "approved"
REJECTED = "rejected"


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Incident:
    """A postmortem-bearing incident — one row of the ``incidents`` table."""

    team_id: str
    title: str
    error_codes: List[str] = field(default_factory=list)
    cause: str = ""
    fix: str = ""
    postmortem: str = ""
    status: str = DRAFT  # draft | approved | rejected
    source_tool: str = ""
    service: str = ""
    call_url: str = ""
    url: str = ""
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team_id": self.team_id,
            "title": self.title,
            "error_codes": list(self.error_codes),
            "cause": self.cause,
            "fix": self.fix,
            "postmortem": self.postmortem,
            "status": self.status,
            "source_tool": self.source_tool,
            "service": self.service,
            "call_url": self.call_url,
            "url": self.url,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
        }


@dataclass
class Chunk:
    """One searchable unit — one row of the ``chunks`` table.

    ``team_id`` is carried on every chunk so the permission filter (Story 20)
    can restrict retrieval before ranking runs.
    """

    source_id: str  # the incident or runbook this chunk came from
    team_id: str
    section: str
    content: str
    embedding: List[float] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "team_id": self.team_id,
            "section": self.section,
            "content": self.content,
            # Embeddings are large; expose only their size over the wire.
            "embedding_dim": len(self.embedding),
        }


@dataclass
class Alert:
    """A monitoring alert, normalized so every tool produces the same shape.

    New Relic and Prometheus Alertmanager both map into this record (Story 33):
    source tool, service, error code, open/close time and a link back.
    """

    source_tool: str
    service: str
    error_code: str
    team_id: str
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    url: str = ""
    id: str = field(default_factory=new_id)

    @property
    def is_closed(self) -> bool:
        """A closed alert is a resolved incident ready for capture (Story 31)."""

        return bool(self.closed_at)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_tool": self.source_tool,
            "service": self.service,
            "error_code": self.error_code,
            "team_id": self.team_id,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "url": self.url,
            "is_closed": self.is_closed,
        }
