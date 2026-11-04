"""Story 23 — Muse Spark cited answer with past fix and live status.

Acceptance criteria: Answer gives the past fix and cause plus the current error
count from the team's monitoring tool; every claim links to a postmortem or
monitoring error. Suspect commits are added when that story is done, and the
answer still works without them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .citations import Citation
from .meta_client import MetaModelClient, MetaModelError

SYSTEM_PROMPT = (
    "You are Muse Spark answering an on-call engineer about a firing alert. "
    "Use only the provided past incident(s), live monitoring status, and (if "
    "present) recent deploys and suspect commits. State the past cause and the "
    "fix that worked, then the current error count. Every claim must cite one of "
    "the provided sources by its [n] marker. If the evidence does not support a "
    "claim, do not make it. Keep it to a few sentences."
)


@dataclass
class MatchedIncident:
    """A past incident retrieved by hybrid search."""

    title: str
    cause: str
    fix: str
    url: str
    score: float


@dataclass
class LiveStatus:
    """Current status pulled from the team's monitoring tool."""

    error_code: str
    error_count: int
    url: str


@dataclass
class Answer:
    """A cited answer ready for the UI."""

    text: str
    citations: List[Citation] = field(default_factory=list)
    no_match: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "citations": [c.to_dict() for c in self.citations],
            "no_match": self.no_match,
        }


class AnswerBuilder:
    """Builds a cited answer from retrieved incidents plus live status."""

    def __init__(self, client: MetaModelClient, no_match_threshold: float = 0.55):
        self.client = client
        self.no_match_threshold = no_match_threshold

    def build(
        self,
        question: str,
        matches: List[MatchedIncident],
        live_status: LiveStatus,
        suspect_commits: Optional[List[Citation]] = None,
    ) -> Answer:
        """Return a cited Answer, or an honest no-match when nothing scores high.

        ``suspect_commits`` is optional: the answer is complete without it and
        simply gains extra citations when it is supplied.
        """

        best = max((m.score for m in matches), default=0.0)
        if not matches or best < self.no_match_threshold:
            return Answer(text="No similar incident found", no_match=True)

        citations: List[Citation] = []
        evidence_lines = [f"Question: {question}", "", "Past incidents:"]
        for incident in matches:
            citations.append(
                Citation(kind="postmortem", label=incident.title, url=incident.url)
            )
            marker = len(citations)
            evidence_lines.append(
                f"[{marker}] {incident.title} — cause: {incident.cause} "
                f"fix: {incident.fix}"
            )

        citations.append(
            Citation(
                kind="monitoring",
                label=f"{live_status.error_code}: {live_status.error_count} errors now",
                url=live_status.url,
            )
        )
        evidence_lines += [
            "",
            "Live monitoring:",
            f"[{len(citations)}] {live_status.error_code} current error count: "
            f"{live_status.error_count}",
        ]

        for commit in suspect_commits or []:
            citations.append(commit)
            evidence_lines.append(f"[{len(citations)}] suspect commit: {commit.label}")

        prompt = "\n".join(evidence_lines)
        try:
            text = self.client.complete(prompt, system=SYSTEM_PROMPT)
        except MetaModelError:
            # Deterministic fallback so an on-call engineer still gets the facts
            # with citations even if Muse Spark is unavailable.
            text = (
                f"Past cause: {matches[0].cause} [1]. "
                f"Fix that worked: {matches[0].fix} [1]. "
                f"Currently {live_status.error_count} "
                f"{live_status.error_code} errors [{len(matches) + 1}]."
            )

        return Answer(text=text, citations=citations, no_match=False)
