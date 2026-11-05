"""Stories 17 & 18 — the indexer that turns approved content into chunks.

Story 17 (Kafka consumer that chunks, embeds and indexes): on
``postmortem.approved`` the consumer writes chunks carrying team_id, text and
embedding; the incident becomes searchable; reprocessing the same event is safe.

Story 18 (re-index only the changed runbook section): a ``document.changed``
event replaces only that section's chunks, so the next answer cites the new
text.

The indexer reuses the AI layer's :class:`~incident_memory_ai.embeddings.Embedder`
so chunks are embedded exactly the way the recall path embeds queries.
"""

from __future__ import annotations

from typing import List, Tuple

from .events import DOCUMENT_CHANGED, POSTMORTEM_APPROVED, EventBus
from .models import Chunk, Incident
from .store import InMemoryStore


class Indexer:
    """Consumes capture/edit events and maintains the chunks table."""

    def __init__(self, store: InMemoryStore, embedder) -> None:
        self.store = store
        self.embedder = embedder

    def subscribe(self, bus: EventBus) -> None:
        """Wire this indexer to the event bus (like joining a consumer group)."""

        bus.subscribe(POSTMORTEM_APPROVED, self.on_postmortem_approved)
        bus.subscribe(DOCUMENT_CHANGED, self.on_document_changed)

    # --- event handlers ------------------------------------------------------
    def on_postmortem_approved(self, payload: dict) -> None:
        incident = self.store.get_incident(payload["incident_id"])
        if incident is not None:
            self.index_incident(incident)

    def on_document_changed(self, payload: dict) -> None:
        self.index_section(
            source_id=payload["source_id"],
            team_id=payload["team_id"],
            section=payload["section"],
            content=payload["content"],
        )

    # --- indexing ------------------------------------------------------------
    def index_incident(self, incident: Incident) -> List[Chunk]:
        """(Re)index an incident's postmortem.

        Existing chunks for the incident are cleared first, so reprocessing the
        same ``postmortem.approved`` event leaves exactly one set of chunks
        (Story 17's "reprocessing the same event is safe").
        """

        self.store.delete_chunks_for_source(incident.id)
        written: List[Chunk] = []
        for section, text in self._sections(incident):
            chunk = Chunk(
                source_id=incident.id,
                team_id=incident.team_id,
                section=section,
                content=text,
                embedding=self.embedder.embed(text),
            )
            self.store.put_chunk(chunk)
            written.append(chunk)
        return written

    def index_section(
        self, source_id: str, team_id: str, section: str, content: str
    ) -> Chunk:
        """Replace just one section's chunks (Story 18)."""

        self.store.delete_chunks_for_source(source_id, section=section)
        chunk = Chunk(
            source_id=source_id,
            team_id=team_id,
            section=section,
            content=content,
            embedding=self.embedder.embed(content),
        )
        self.store.put_chunk(chunk)
        return chunk

    @staticmethod
    def _sections(incident: Incident) -> List[Tuple[str, str]]:
        """Split an incident into the sections worth indexing separately.

        The title and error codes carry the exact strings keyword search needs;
        cause and fix carry the prose vector search needs.
        """

        header = incident.title
        if incident.error_codes:
            header = f"{incident.title} ({', '.join(incident.error_codes)})"
        sections = [("title", header)]
        if incident.cause:
            sections.append(("cause", incident.cause))
        if incident.fix:
            sections.append(("fix", incident.fix))
        if incident.postmortem:
            sections.append(("postmortem", incident.postmortem))
        return sections
