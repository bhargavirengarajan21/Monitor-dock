"""Story 12 — Muse Spark drafts a postmortem from the evidence.

Acceptance criteria: From the New Relic error, the deploy and the fix PR, Muse
Spark returns JSON with title, cause, fix, owner, error codes and source links;
invalid JSON is retried once and then flagged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .meta_client import MetaModelClient, MetaModelError

REQUIRED_FIELDS = ("title", "cause", "fix", "owner", "error_codes", "sources")

SYSTEM_PROMPT = (
    "You are Muse Spark drafting an incident postmortem for engineer review. "
    "Read the evidence and return ONLY a JSON object with these keys: "
    "title (string), cause (string), fix (string), owner (string), "
    "error_codes (array of strings), sources (array of {label, url}). "
    "Every factual claim in cause and fix must be supported by an entry in sources. "
    "Do not invent URLs; use only those present in the evidence."
)


class PostmortemError(RuntimeError):
    """Raised when a usable postmortem could not be produced."""


@dataclass
class Evidence:
    """The inputs Muse Spark drafts from."""

    new_relic_error: str
    deploy: str
    fix_pr: str
    extra: dict = field(default_factory=dict)

    def to_prompt(self) -> str:
        lines = [
            "New Relic error:",
            self.new_relic_error,
            "",
            "Related deploy (GitHub Actions):",
            self.deploy,
            "",
            "Fix PR:",
            self.fix_pr,
        ]
        for key, value in self.extra.items():
            lines += ["", f"{key}:", str(value)]
        return "\n".join(lines)


def _validate(draft: dict) -> List[str]:
    """Return a list of problems; empty means the draft is well formed."""

    problems = []
    for name in REQUIRED_FIELDS:
        if name not in draft:
            problems.append(f"missing field '{name}'")
    if "error_codes" in draft and not isinstance(draft["error_codes"], list):
        problems.append("error_codes must be a list")
    if "sources" in draft:
        if not isinstance(draft["sources"], list) or not draft["sources"]:
            problems.append("sources must be a non-empty list")
        else:
            for src in draft["sources"]:
                if not isinstance(src, dict) or "url" not in src:
                    problems.append("each source needs a url")
                    break
    return problems


class PostmortemDrafter:
    """Drafts a structured postmortem, retrying invalid JSON once."""

    def __init__(self, client: MetaModelClient):
        self.client = client

    def draft(self, evidence: Evidence) -> dict:
        """Return a validated postmortem dict (status defaults to 'draft').

        Retries once on invalid JSON or a malformed draft, then flags failure by
        raising PostmortemError so a human never sees a half-formed draft.
        """

        prompt = evidence.to_prompt()
        last_error: Optional[str] = None

        for attempt in range(2):  # initial try + one retry
            try:
                draft = self.client.complete_json(prompt, system=SYSTEM_PROMPT)
            except MetaModelError as exc:
                last_error = str(exc)
                continue

            problems = _validate(draft)
            if not problems:
                draft.setdefault("status", "draft")
                return draft
            last_error = "; ".join(problems)

        raise PostmortemError(
            f"Muse Spark did not return a valid postmortem after a retry: {last_error}"
        )
