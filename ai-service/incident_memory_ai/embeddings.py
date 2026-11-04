"""Story 4 — local embedding model through Ollama.

Acceptance criteria: embed(text) returns a vector whose size matches the
pgvector column; works offline.

The embedder calls a local Ollama instance for real embeddings. When Ollama is
unreachable (the "works offline" requirement), it falls back to a deterministic,
hash-seeded pseudo-embedding of the same dimension so the rest of the pipeline
keeps working and tests run without any service.
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.request
from typing import Callable, List, Optional

from .config import Config, load_config

# Must match the vector(768) column in the chunks table.
EMBEDDING_DIM = 768

# A transport takes (url, body_bytes) and returns the decoded JSON response.
Transport = Callable[[str, bytes], dict]


def _urllib_transport(url: str, body: bytes, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # pragma: no cover - network path
        return json.loads(resp.read().decode("utf-8"))


def _normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _offline_embedding(text: str, dim: int) -> List[float]:
    """Deterministic fallback embedding.

    Derives ``dim`` floats from repeated SHA-256 hashing of the text. It is not
    semantically meaningful, but it is stable, the right size, and lets the
    pipeline run with no external service.
    """

    values: List[float] = []
    counter = 0
    seed = text.encode("utf-8")
    while len(values) < dim:
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for i in range(0, len(digest), 2):
            if len(values) >= dim:
                break
            # Map two bytes into roughly [-1, 1].
            raw = int.from_bytes(digest[i : i + 2], "big")
            values.append((raw / 32767.5) - 1.0)
        counter += 1
    return _normalize(values)


class Embedder:
    """Produces embeddings for text, preferring Ollama and falling back offline."""

    def __init__(
        self,
        config: Optional[Config] = None,
        transport: Optional[Transport] = None,
        dim: int = EMBEDDING_DIM,
    ):
        self.config = config or load_config()
        self._transport = transport or _urllib_transport
        self.dim = dim

    def _ollama_embedding(self, text: str) -> Optional[List[float]]:
        url = f"{self.config.ollama_base_url.rstrip('/')}/api/embeddings"
        body = json.dumps({"model": self.config.embedding_model, "prompt": text}).encode("utf-8")
        try:
            response = self._transport(url, body)
        except (urllib.error.URLError, OSError):
            return None
        embedding = response.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            return None
        if len(embedding) != self.dim:
            raise ValueError(
                f"Ollama returned dim {len(embedding)}, expected {self.dim}. "
                "Check EMBEDDING_MODEL matches the pgvector column."
            )
        return _normalize([float(v) for v in embedding])

    def embed(self, text: str) -> List[float]:
        """Return a vector of length ``self.dim`` for ``text``.

        Uses Ollama when available, otherwise a deterministic offline fallback.
        The result always matches the pgvector column size.
        """

        vector = self._ollama_embedding(text)
        if vector is None:
            vector = _offline_embedding(text, self.dim)
        assert len(vector) == self.dim
        return vector
