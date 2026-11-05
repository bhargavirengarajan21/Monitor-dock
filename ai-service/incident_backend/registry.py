"""Story 36 — team tool registry.

Each team is registered with the monitoring tool it uses and the other teams it
is allowed to read. The registry is the single source for two things the recall
path needs:

* a :class:`~incident_backend.permissions.PermissionPolicy` (which teams a team
  may see — Story 20), and
* which connector a team's alerts come from (Story 29's shared contract), so a
  new team or tool is added as data, not code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .permissions import PermissionPolicy


@dataclass
class TeamRegistration:
    """One team's monitoring tool and read visibility."""

    team_id: str
    tool: str
    visible_teams: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "team_id": self.team_id,
            "tool": self.tool,
            "visible_teams": list(self.visible_teams),
        }


class TeamRegistry:
    """Holds team registrations and derives the permission policy from them."""

    def __init__(self) -> None:
        self._teams: Dict[str, TeamRegistration] = {}

    def register(self, team_id: str, tool: str, visible_teams: List[str] | None = None) -> None:
        self._teams[team_id] = TeamRegistration(
            team_id=team_id, tool=tool, visible_teams=list(visible_teams or [])
        )

    def tool_for(self, team_id: str) -> str:
        reg = self._teams.get(team_id)
        if reg is None:
            raise KeyError(f"Team {team_id!r} is not registered")
        return reg.tool

    def teams(self) -> List[TeamRegistration]:
        return list(self._teams.values())

    def permission_policy(self) -> PermissionPolicy:
        """Build the permission policy from every team's visible_teams."""

        return PermissionPolicy(
            {reg.team_id: reg.visible_teams for reg in self._teams.values()}
        )
