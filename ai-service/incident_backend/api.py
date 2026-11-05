"""Story 1 — scaffold the backend HTTP API.

A thin HTTP layer over :class:`~incident_backend.backend.IncidentBackend`, built
on the standard library's ``http.server`` so the backend keeps the AI layer's
no-third-party-dependency promise and runs with ``python -m incident_backend``.
The routing logic lives in :func:`dispatch` so it can be unit-tested without
opening a socket.

Endpoints:

* ``GET  /health``                         liveness check
* ``POST /webhooks/alert?source=&team=``   New Relic / Prometheus webhook (Story 9, 19)
* ``POST /ask``                            free-text question (Story 19, 40)
* ``POST /incidents``                      create a draft incident
* ``GET  /incidents?status=draft``         list incidents for the approve screen (Story 14)
* ``GET  /incidents/{id}``                 fetch one draft to review (Story 14)
* ``POST /postmortems/{id}/approve``       approve a draft (Story 15)
* ``POST /postmortems/{id}/reject``        reject a draft (Story 14)
* ``GET  /answers/{alert_id}``             re-load a saved answer (Story 19, 24)

``/incidents`` and ``/postmortems`` address the same records; the first is the
noun the capture UI creates and lists, the second is the review action on one.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .backend import IncidentBackend

# The single-page UI (Stories 14, 24, 37, 38, 39) lives next to the package and
# is served by the backend so the whole app runs from one process.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _static_file(route: str) -> Optional[Tuple[str, bytes]]:
    """Return (content_type, bytes) for a static UI route, or None."""

    name = "index.html" if route in ("/", "/index.html") else route.lstrip("/")
    path = (FRONTEND_DIR / name).resolve()
    # Keep reads inside the frontend directory.
    if FRONTEND_DIR not in path.parents and path != FRONTEND_DIR / name:
        return None
    if not path.is_file():
        return None
    content_type = "text/html" if path.suffix == ".html" else "text/plain"
    if path.suffix == ".js":
        content_type = "application/javascript"
    elif path.suffix == ".css":
        content_type = "text/css"
    return content_type, path.read_bytes()


class ApiError(Exception):
    """An HTTP error with a status code and message."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def dispatch(backend: IncidentBackend, method: str, path: str, body: dict) -> Tuple[int, dict]:
    """Route one request to the backend and return (status, json_body).

    Pure function of its arguments so tests can exercise every route without a
    live server.
    """

    parsed = urlparse(path)
    route = parsed.path.rstrip("/") or "/"
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

    if method == "GET" and route == "/health":
        return 200, {"status": "ok"}

    if method == "GET" and route == "/teams":
        registry = getattr(backend, "registry", None)
        teams = [t.to_dict() for t in registry.teams()] if registry else []
        return 200, {"teams": teams}

    if method == "POST" and route == "/webhooks/alert":
        source = query.get("source") or body.get("source")
        team = query.get("team") or body.get("team_id")
        if not source or not team:
            raise ApiError(400, "source and team are required")
        payload = body.get("payload", body)
        return 200, backend.ingest_alert(source, payload, team)

    if method == "POST" and route == "/ask":
        question = body.get("question")
        team = body.get("team_id")
        if not question or not team:
            raise ApiError(400, "question and team_id are required")
        return 200, backend.ask(
            question, team, body.get("service", ""), body.get("error_code", "")
        )

    if method == "POST" and route == "/incidents":
        if not body.get("team_id") or not body.get("title"):
            raise ApiError(400, "team_id and title are required")
        return 201, backend.create_incident(body).to_dict()

    if method == "GET" and route == "/incidents":
        return 200, {"incidents": backend.list_incidents(query.get("status"))}

    if method == "GET" and route.startswith("/incidents/"):
        incident_id = route[len("/incidents/") :]
        incident = backend.get_incident(incident_id)
        if incident is None:
            raise ApiError(404, f"No incident {incident_id!r}")
        return 200, incident

    if method == "POST" and route.startswith("/postmortems/") and route.endswith("/approve"):
        incident_id = route[len("/postmortems/") : -len("/approve")]
        try:
            published = backend.approve(incident_id)
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        return 200, {"incident_id": incident_id, "published": published}

    if method == "POST" and route.startswith("/postmortems/") and route.endswith("/reject"):
        incident_id = route[len("/postmortems/") : -len("/reject")]
        try:
            backend.reject(incident_id)
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        return 200, {"incident_id": incident_id, "status": "rejected"}

    if method == "GET" and route.startswith("/answers/"):
        alert_id = route[len("/answers/") :]
        answer = backend.saved_answer(alert_id)
        if answer is None:
            raise ApiError(404, f"No saved answer for alert {alert_id!r}")
        return 200, answer

    raise ApiError(404, f"No route for {method} {route}")


def make_handler(backend: IncidentBackend):
    """Build a BaseHTTPRequestHandler bound to a backend instance."""

    class Handler(BaseHTTPRequestHandler):
        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(body, dict):
                    raise ApiError(400, "request body must be a JSON object")
                status, payload = dispatch(backend, method, self.path, body)
            except ApiError as exc:
                status, payload = exc.status, {"error": exc.message}
            except json.JSONDecodeError:
                status, payload = 400, {"error": "invalid JSON body"}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _serve_static(self) -> bool:
            """Serve the UI for a GET route; return True if handled."""

            route = urlparse(self.path).path
            static = _static_file(route)
            if static is None:
                return False
            content_type, data = static
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return True

        def do_GET(self) -> None:  # noqa: N802 - required name
            if self._serve_static():
                return
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802 - required name
            self._handle("POST")

        def log_message(self, *args) -> None:  # silence default stderr logging
            pass

    return Handler


def serve(backend: IncidentBackend | None = None, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the HTTP server (blocking).

    With no backend passed, boots pre-seeded with the demo dataset when
    ``SEED_DEMO`` is set, otherwise empty.
    """

    if backend is None:
        from .seed import seed_backend, seed_enabled

        backend = seed_backend() if seed_enabled() else IncidentBackend()
    server = HTTPServer((host, port), make_handler(backend))
    seeded = " (seeded with demo data)" if getattr(backend, "registry", None) else ""
    print(f"Incident Memory backend listening on http://{host}:{port}{seeded}")
    server.serve_forever()
