"""Story 29 — connector contract shared by every monitoring tool.

Acceptance criteria: each connector is a small server exposing the same tools —
``get_alert``, ``get_errors(service, window)`` and ``get_error_rate(service,
window)`` — so a new tool can be added without changing capture or recall code.

The recall path depends only on the :class:`Connector` protocol below, never on
a specific vendor. :class:`InMemoryConnector` implements the contract with canned
data so the whole flow runs offline; a New Relic connector (Story 34) or a
Prometheus/Alertmanager connector (Story 35) implements the same three methods
against a real backend and drops in without touching recall or capture.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol

from .models import Alert


class Connector(Protocol):
    """The single interface every monitoring tool exposes."""

    name: str

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Fetch a normalized alert by id, or None if unknown."""
        ...

    def get_errors(self, service: str, window: str) -> List[dict]:
        """Recent errors for a service in a time window.

        Each error is ``{message, trace, count, url}``.
        """
        ...

    def get_error_rate(self, service: str, window: str) -> float:
        """Errors-per-minute for a service over the window."""
        ...


class InMemoryConnector:
    """A canned connector implementing the contract for offline runs and tests."""

    def __init__(
        self,
        name: str = "in-memory",
        alerts: Optional[Dict[str, Alert]] = None,
        errors: Optional[Dict[str, List[dict]]] = None,
        error_rates: Optional[Dict[str, float]] = None,
    ) -> None:
        self.name = name
        self._alerts: Dict[str, Alert] = dict(alerts or {})
        self._errors: Dict[str, List[dict]] = dict(errors or {})
        self._error_rates: Dict[str, float] = dict(error_rates or {})

    def add_alert(self, alert: Alert) -> None:
        self._alerts[alert.id] = alert

    def set_errors(self, service: str, errors: List[dict]) -> None:
        self._errors[service] = errors

    def set_error_rate(self, service: str, rate: float) -> None:
        self._error_rates[service] = rate

    # --- Connector contract --------------------------------------------------
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self._alerts.get(alert_id)

    def get_errors(self, service: str, window: str) -> List[dict]:
        return list(self._errors.get(service, []))

    def get_error_rate(self, service: str, window: str) -> float:
        if service in self._error_rates:
            return self._error_rates[service]
        # Fall back to the count carried on the known errors for the service.
        return float(sum(e.get("count", 0) for e in self._errors.get(service, [])))
