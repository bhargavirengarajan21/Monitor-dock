"""Story 20 — permission filter by team.

Acceptance criteria: search only returns chunks whose team_id is allowed for the
asking team; a test proves another team's postmortem is never returned.

The policy is applied *before* retrieval (the store is asked only for allowed
chunks), so an un-permitted document can never reach ranking or the model.
"""

from __future__ import annotations

from typing import Dict, Iterable, Set


class PermissionPolicy:
    """Maps an asking team to the set of team_ids it is allowed to read.

    By default a team can read only its own documents. A visibility map can
    grant extra teams (for shared postmortems) without changing search code.
    """

    def __init__(self, visibility: Dict[str, Iterable[str]] | None = None) -> None:
        self._visibility: Dict[str, Set[str]] = {
            team: set(allowed) for team, allowed in (visibility or {}).items()
        }

    def allowed_teams(self, asking_team: str) -> Set[str]:
        """Teams whose chunks ``asking_team`` may see (always includes itself)."""

        allowed = set(self._visibility.get(asking_team, set()))
        allowed.add(asking_team)
        return allowed

    def grant(self, asking_team: str, other_team: str) -> None:
        """Let ``asking_team`` also read ``other_team``'s documents."""

        self._visibility.setdefault(asking_team, set()).add(other_team)
