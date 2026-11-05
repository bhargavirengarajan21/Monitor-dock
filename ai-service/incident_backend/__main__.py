"""Run the backend HTTP server: ``python -m incident_backend``."""

from __future__ import annotations

import os

from .api import serve

if __name__ == "__main__":
    serve(port=int(os.environ.get("PORT", "8000")))
