"""In-memory store for incidents, chunks and saved answers (Story 16).

The README's storage is Postgres + pgvector, but the AI layer deliberately runs
offline with no third-party services, and the backend keeps that promise: this
store models the same two tables (incidents, chunks) in process so the whole
recall and capture flow runs — and is tested — without a database. Swapping in a
real Postgres-backed store means re-implementing this same small interface.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .models import Chunk, Incident


class InMemoryStore:
    """Holds incidents, chunks and saved answers keyed by id."""

    def __init__(self) -> None:
        self._incidents: Dict[str, Incident] = {}
        self._chunks: Dict[str, Chunk] = {}
        self._answers: Dict[str, dict] = {}

    # --- incidents -----------------------------------------------------------
    def save_incident(self, incident: Incident) -> Incident:
        self._incidents[incident.id] = incident
        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def incidents(self) -> List[Incident]:
        return list(self._incidents.values())

    # --- chunks --------------------------------------------------------------
    def put_chunk(self, chunk: Chunk) -> Chunk:
        self._chunks[chunk.id] = chunk
        return chunk

    def delete_chunks_for_source(
        self, source_id: str, section: Optional[str] = None
    ) -> int:
        """Delete chunks for a source, optionally only one section.

        Deleting all chunks for a source makes re-indexing idempotent
        (Story 17); deleting a single section lets a runbook edit replace only
        that section (Story 18). Returns the number of chunks removed.
        """

        doomed = [
            cid
            for cid, chunk in self._chunks.items()
            if chunk.source_id == source_id
            and (section is None or chunk.section == section)
        ]
        for cid in doomed:
            del self._chunks[cid]
        return len(doomed)

    def chunks_for_teams(self, allowed_team_ids: Iterable[str]) -> List[Chunk]:
        """Return only chunks whose team_id is in the allowed set (Story 20)."""

        allowed = set(allowed_team_ids)
        return [c for c in self._chunks.values() if c.team_id in allowed]

    def all_chunks(self) -> List[Chunk]:
        return list(self._chunks.values())

    # --- answers -------------------------------------------------------------
    def save_answer(self, alert_id: str, answer: dict) -> None:
        self._answers[alert_id] = answer

    def get_answer(self, alert_id: str) -> Optional[dict]:
        return self._answers.get(alert_id)
