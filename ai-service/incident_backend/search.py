"""Story 21 — hybrid search: full-text plus pgvector.

Acceptance criteria: keyword and vector results are merged with reciprocal rank
fusion; a search for the exact code ERR_PAYMENT_409 ranks the matching incident
first.

Keyword search catches exact strings (error codes), vector search catches
incidents described in different words, and the two ranked lists are merged with
reciprocal rank fusion (RRF). The permission filter (Story 20) runs first, so
only allowed chunks are ever ranked.

The pgvector column is modelled by the embedding carried on each chunk; cosine
similarity stands in for pgvector's nearest-neighbour search, keeping the whole
thing in process and offline.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List

from .models import Chunk
from .permissions import PermissionPolicy
from .store import InMemoryStore

# RRF constant; the standard default that keeps any single list from dominating.
RRF_K = 60
# Exact-string matches (error codes) are the whole point of keeping keyword
# search, so the keyword list is weighted above the vector list in the fusion.
KEYWORD_WEIGHT = 2.0
VECTOR_WEIGHT = 1.0

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    # Underscores are kept so an error code like ERR_PAYMENT_409 stays one token
    # instead of fragmenting into "err", "payment", "409".
    return _TOKEN_RE.findall((text or "").lower())


def _is_distinctive(token: str) -> bool:
    """A token that reads like an identifier/error code, not a common word."""

    return len(token) >= 5 and bool(re.search(r"[0-9_]", token))


def keyword_score(query_tokens: List[str], chunk: Chunk) -> float:
    """Fraction of query tokens present in the chunk, boosted for exact codes.

    Returns a value in [0, 1]. A shared distinctive token (an error code) pins
    the score near the top, so the exact-code query ranks its incident first.
    """

    if not query_tokens:
        return 0.0
    content = set(_tokenize(chunk.content))
    overlap = [t for t in query_tokens if t in content]
    score = len(overlap) / len(query_tokens)
    if any(_is_distinctive(t) for t in overlap):
        score = max(score, 0.9)
    return score


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class SearchHit:
    """A ranked chunk with a normalized [0, 1] relevance score.

    ``score`` is the strongest single signal (keyword or vector) and is what the
    no-match threshold (Story 22) compares against; ``rank`` reflects the fused
    RRF ordering.
    """

    chunk: Chunk
    score: float
    rank: int


class HybridSearch:
    """Merges keyword and vector rankings with reciprocal rank fusion."""

    def __init__(
        self,
        store: InMemoryStore,
        embedder,
        permissions: PermissionPolicy | None = None,
        rrf_k: int = RRF_K,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.permissions = permissions or PermissionPolicy()
        self.rrf_k = rrf_k

    def search(self, query: str, team_id: str, limit: int = 5) -> List[SearchHit]:
        allowed = self.permissions.allowed_teams(team_id)
        candidates = self.store.chunks_for_teams(allowed)
        if not candidates:
            return []

        query_tokens = _tokenize(query)
        query_vector = self.embedder.embed(query)

        kw_scores = {c.id: keyword_score(query_tokens, c) for c in candidates}
        vec_scores = {c.id: cosine(query_vector, c.embedding) for c in candidates}

        kw_ranked = sorted(candidates, key=lambda c: kw_scores[c.id], reverse=True)
        vec_ranked = sorted(candidates, key=lambda c: vec_scores[c.id], reverse=True)

        fused: dict[str, float] = {}
        for rank, chunk in enumerate(kw_ranked):
            fused[chunk.id] = fused.get(chunk.id, 0.0) + KEYWORD_WEIGHT / (
                self.rrf_k + rank + 1
            )
        for rank, chunk in enumerate(vec_ranked):
            fused[chunk.id] = fused.get(chunk.id, 0.0) + VECTOR_WEIGHT / (
                self.rrf_k + rank + 1
            )

        by_id = {c.id: c for c in candidates}
        # Normalized relevance: cosine is in [-1, 1], mapped to [0, 1].
        normalized = {
            cid: max(kw_scores[cid], (vec_scores[cid] + 1.0) / 2.0) for cid in by_id
        }

        order = sorted(
            by_id.values(),
            key=lambda c: (fused[c.id], kw_scores[c.id], normalized[c.id]),
            reverse=True,
        )
        return [
            SearchHit(chunk=c, score=normalized[c.id], rank=i)
            for i, c in enumerate(order[:limit])
        ]
