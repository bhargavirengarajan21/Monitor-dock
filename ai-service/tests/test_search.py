"""Stories 20 & 21 — hybrid search and the team permission filter."""

from incident_backend.models import Chunk
from incident_backend.permissions import PermissionPolicy
from incident_backend.search import HybridSearch
from incident_backend.store import InMemoryStore
from incident_memory_ai.embeddings import Embedder


def _store_with_incidents():
    store = InMemoryStore()
    embedder = Embedder()
    # The matching incident carries the exact error code.
    store.put_chunk(
        Chunk(
            source_id="inc-409",
            team_id="payments",
            section="title",
            content="Payment failures ERR_PAYMENT_409 after idempotency change",
            embedding=embedder.embed("ERR_PAYMENT_409 idempotency"),
        )
    )
    store.put_chunk(
        Chunk(
            source_id="inc-timeout",
            team_id="payments",
            section="title",
            content="Checkout latency spike from a slow database query",
            embedding=embedder.embed("checkout latency database"),
        )
    )
    return store, embedder


def test_exact_error_code_ranks_matching_incident_first():
    store, embedder = _store_with_incidents()
    search = HybridSearch(store, embedder)

    hits = search.search("ERR_PAYMENT_409", team_id="payments")

    assert hits
    assert hits[0].chunk.source_id == "inc-409"
    assert hits[0].score >= 0.55  # strong enough to clear the no-match threshold


def test_permission_filter_hides_other_teams():
    store = InMemoryStore()
    embedder = Embedder()
    store.put_chunk(
        Chunk(
            source_id="secret",
            team_id="infra",
            section="title",
            content="ERR_PAYMENT_409 postmortem that payments must not see",
            embedding=embedder.embed("ERR_PAYMENT_409"),
        )
    )
    search = HybridSearch(store, embedder, PermissionPolicy())

    # The payments team searches for the exact code but owns no chunks.
    hits = search.search("ERR_PAYMENT_409", team_id="payments")

    assert hits == []  # another team's postmortem is never returned


def test_granted_visibility_lets_a_team_see_shared_postmortems():
    store = InMemoryStore()
    embedder = Embedder()
    store.put_chunk(
        Chunk(
            source_id="shared",
            team_id="infra",
            section="title",
            content="ERR_PAYMENT_409 shared runbook",
            embedding=embedder.embed("ERR_PAYMENT_409"),
        )
    )
    policy = PermissionPolicy({"payments": ["infra"]})
    search = HybridSearch(store, embedder, policy)

    hits = search.search("ERR_PAYMENT_409", team_id="payments")

    assert [h.chunk.source_id for h in hits] == ["shared"]
