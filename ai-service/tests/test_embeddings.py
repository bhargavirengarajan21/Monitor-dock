"""Story 4 — local embedding model through Ollama."""

from incident_memory_ai.config import load_config
from incident_memory_ai.embeddings import Embedder, EMBEDDING_DIM


def test_offline_embedding_matches_column_size():
    # No transport reaches Ollama -> offline fallback, works offline.
    def failing_transport(url, body):
        raise OSError("ollama not running")

    embedder = Embedder(config=load_config({}), transport=failing_transport)
    vector = embedder.embed("ERR_PAYMENT_409 on payment-service")

    assert len(vector) == EMBEDDING_DIM


def test_offline_embedding_is_deterministic():
    embedder = Embedder(config=load_config({}), transport=lambda u, b: (_ for _ in ()).throw(OSError()))
    a = embedder.embed("same text")
    b = embedder.embed("same text")
    c = embedder.embed("different text")
    assert a == b
    assert a != c


def test_uses_ollama_when_available():
    expected = [0.01 * i for i in range(EMBEDDING_DIM)]

    def transport(url, body):
        assert url.endswith("/api/embeddings")
        return {"embedding": expected}

    embedder = Embedder(config=load_config({}), transport=transport)
    vector = embedder.embed("hello")
    assert len(vector) == EMBEDDING_DIM


def test_rejects_wrong_dimension_from_ollama():
    def transport(url, body):
        return {"embedding": [0.1, 0.2, 0.3]}  # wrong size

    embedder = Embedder(config=load_config({}), transport=transport)
    try:
        embedder.embed("hello")
    except ValueError:
        return
    raise AssertionError("expected ValueError on dimension mismatch")
