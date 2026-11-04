"""Shared citation type used by postmortems and answers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    """A single linkable source backing a claim."""

    kind: str  # "postmortem" | "monitoring" | "deploy" | "commit" | "runbook" | "pr"
    label: str
    url: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label, "url": self.url}
