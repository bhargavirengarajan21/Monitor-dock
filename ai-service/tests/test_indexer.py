"""Stories 17 & 18 — the indexer chunks, embeds, and re-indexes safely."""

from incident_backend.events import DOCUMENT_CHANGED, EventBus
from incident_backend.indexer import Indexer
from incident_backend.models import Incident
from incident_backend.store import InMemoryStore
from incident_memory_ai.embeddings import EMBEDDING_DIM, Embedder


def _incident():
    return Incident(
        team_id="payments",
        title="Payment 409",
        error_codes=["ERR_PAYMENT_409"],
        cause="Idempotency key became non-unique.",
        fix="Reverted the key change in PR #42.",
    )


def test_index_incident_writes_chunks_with_team_and_embedding():
    store = InMemoryStore()
    indexer = Indexer(store, Embedder())

    chunks = indexer.index_incident(_incident())

    assert chunks
    assert all(c.team_id == "payments" for c in chunks)
    assert all(len(c.embedding) == EMBEDDING_DIM for c in chunks)


def test_reprocessing_the_same_event_is_safe():
    store = InMemoryStore()
    bus = EventBus()
    indexer = Indexer(store, Embedder())
    indexer.subscribe(bus)
    incident = store.save_incident(_incident())

    indexer.on_postmortem_approved({"incident_id": incident.id})
    count_after_first = len(store.all_chunks())
    indexer.on_postmortem_approved({"incident_id": incident.id})
    count_after_second = len(store.all_chunks())

    assert count_after_first > 0
    assert count_after_second == count_after_first  # no duplicates


def test_document_changed_replaces_only_that_section():
    store = InMemoryStore()
    indexer = Indexer(store, Embedder())
    indexer.index_section("runbook-1", "payments", "rollback", "old rollback steps")
    indexer.index_section("runbook-1", "payments", "contacts", "on-call pager")

    indexer.on_document_changed(
        {
            "source_id": "runbook-1",
            "team_id": "payments",
            "section": "rollback",
            "content": "new rollback steps",
        }
    )

    rollback = [c for c in store.all_chunks() if c.section == "rollback"]
    contacts = [c for c in store.all_chunks() if c.section == "contacts"]
    assert len(rollback) == 1
    assert rollback[0].content == "new rollback steps"
    assert len(contacts) == 1  # untouched section survives
    assert contacts[0].content == "on-call pager"
