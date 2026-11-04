"""Story 40 — read-only assistant refuses actions.

Acceptance criteria: Requests like 'revert the deploy' or 'restart the service'
get a clear refusal explaining Incident Memory is read-only, with the relevant
runbook or PR link instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .citations import Citation

# Verbs that would change the production system. Matched as whole words.
ACTION_VERBS = (
    "revert",
    "rollback",
    "roll back",
    "restart",
    "reboot",
    "redeploy",
    "deploy",
    "scale",
    "delete",
    "drop",
    "truncate",
    "kill",
    "stop",
    "start",
    "disable",
    "enable",
    "merge",
    "run",
    "execute",
    "apply",
    "patch",
    "promote",
)

_ACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in ACTION_VERBS) + r")\b", re.IGNORECASE
)

REFUSAL_PREFIX = (
    "Incident Memory is read-only — it recalls how past incidents were fixed but "
    "cannot change the running system."
)


@dataclass
class ActionRefusal:
    """A refusal to act, with pointers to where the action can be done."""

    message: str
    links: List[Citation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"message": self.message, "links": [c.to_dict() for c in self.links]}


class ReadOnlyGuard:
    """Detects action requests and produces a read-only refusal."""

    def is_action_request(self, text: str) -> bool:
        return bool(_ACTION_RE.search(text or ""))

    def refuse(self, request: str, pointers: Optional[List[Citation]] = None) -> ActionRefusal:
        """Build a clear refusal, attaching runbook/PR links when provided."""

        if pointers:
            follow_up = " Here is where that can be done instead:"
        else:
            follow_up = " Check the linked runbook or PR to perform it yourself."
        return ActionRefusal(
            message=f"{REFUSAL_PREFIX}{follow_up}",
            links=list(pointers or []),
        )
