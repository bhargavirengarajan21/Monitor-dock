"""Stories 19 & 22 — the recall flow an alert triggers.

Story 19 (alert webhook starts the recall flow): an incoming alert triggers
recall and the answer is saved and shown in the UI.

Story 22 (no similar incident threshold): if the best score is below
NO_MATCH_THRESHOLD the API returns "No similar incident found" without calling
the model.

The five README steps run here: permission filter (Story 20) → hybrid search
(Story 21) → score check (Story 22) → cited answer (Story 23). The guardrail
(Story 40) covers the free-text question path so a read-only assistant never
appears to act.
"""

from __future__ import annotations

from typing import List, Optional

from incident_memory_ai.answer import AnswerBuilder, Answer, LiveStatus, MatchedIncident
from incident_memory_ai.citations import Citation
from incident_memory_ai.guardrails import ReadOnlyGuard

from .connectors import Connector
from .models import Alert
from .search import HybridSearch, SearchHit
from .store import InMemoryStore


class RecallService:
    """Turns an alert (or a question) into a saved, cited answer."""

    def __init__(
        self,
        store: InMemoryStore,
        search: HybridSearch,
        answer_builder: AnswerBuilder,
        connector: Connector,
        guard: Optional[ReadOnlyGuard] = None,
        window: str = "1h",
    ) -> None:
        self.store = store
        self.search = search
        self.answer_builder = answer_builder
        self.connector = connector
        self.guard = guard or ReadOnlyGuard()
        self.window = window

    def handle_alert(self, alert: Alert) -> dict:
        """Run recall for a firing alert and save the answer (Story 19).

        Returns the facts the UI shows *before* the AI answer (Story 38): the
        matched incidents with their honest similarity scores (Story 39) and the
        live monitoring status, alongside the cited answer.
        """

        query = f"{alert.error_code} {alert.service}".strip()
        result = self._recall(query, alert.team_id, alert.service, alert.error_code, alert.url)
        self.store.save_answer(alert.id, result["answer"])
        return result

    def handle_question(
        self, question: str, team_id: str, service: str, error_code: str
    ) -> dict:
        """Answer a free-text question, refusing action requests (Story 40)."""

        if self.guard.is_action_request(question):
            return {"refusal": self.guard.refuse(question).to_dict()}
        return self._recall(question, team_id, service, error_code, url="")

    # --- internals -----------------------------------------------------------
    def _recall(
        self, query: str, team_id: str, service: str, error_code: str, url: str
    ) -> dict:
        hits = self.search.search(query, team_id, limit=3)
        matches = self._to_matches(hits)
        live_status = self._live_status(service, error_code, url)
        # AnswerBuilder enforces the no-match threshold and skips the model call
        # when the best score is too low (Story 22).
        answer = self.answer_builder.build(query, matches, live_status)
        return {
            "answer": answer.to_dict(),
            # Facts shown first (Story 38) with scores as-is (Story 39).
            "matches": [
                {"title": m.title, "url": m.url, "score": round(m.score, 3)}
                for m in matches
            ],
            "live_status": {
                "error_code": live_status.error_code,
                "error_count": live_status.error_count,
                "url": live_status.url,
            },
        }

    def _to_matches(self, hits: List[SearchHit]) -> List[MatchedIncident]:
        """Collapse chunk hits to one match per incident, keeping the best score."""

        best_by_incident: dict[str, MatchedIncident] = {}
        for hit in hits:
            incident = self.store.get_incident(hit.chunk.source_id)
            if incident is None:
                continue
            existing = best_by_incident.get(incident.id)
            if existing is not None and existing.score >= hit.score:
                continue
            best_by_incident[incident.id] = MatchedIncident(
                title=incident.title,
                cause=incident.cause,
                fix=incident.fix,
                url=incident.url,
                score=hit.score,
            )
        return sorted(best_by_incident.values(), key=lambda m: m.score, reverse=True)

    def _live_status(self, service: str, error_code: str, url: str) -> LiveStatus:
        errors = self.connector.get_errors(service, self.window)
        count = sum(int(e.get("count", 0)) for e in errors)
        live_url = url
        if errors and errors[0].get("url"):
            live_url = errors[0]["url"]
        return LiveStatus(error_code=error_code, error_count=count, url=live_url)
