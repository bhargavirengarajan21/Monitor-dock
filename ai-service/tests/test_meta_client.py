"""Story 3 — Meta Model API client."""

import json

from incident_memory_ai.config import load_config
from incident_memory_ai.meta_client import MetaModelClient, MetaModelError


def _fake_transport(reply_content):
    captured = {}

    def transport(url, headers, body):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json.loads(body.decode("utf-8"))
        return {"choices": [{"message": {"content": reply_content}}]}

    transport.captured = captured
    return transport


def test_reads_config_from_env():
    env = {
        "META_API_BASE_URL": "https://example.test/v1",
        "MODEL_API_KEY": "secret-key",
        "META_CHAT_MODEL": "muse-spark-xl",
    }
    config = load_config(env)
    assert config.meta_api_base_url == "https://example.test/v1"
    assert config.model_api_key == "secret-key"
    assert config.chat_model == "muse-spark-xl"


def test_complete_returns_text_and_sends_key_and_model():
    env = {"MODEL_API_KEY": "secret-key", "META_CHAT_MODEL": "muse-spark-xl",
           "META_API_BASE_URL": "https://example.test/v1"}
    transport = _fake_transport("hello from muse spark")
    client = MetaModelClient(config=load_config(env), transport=transport)

    text = client.complete("hi")

    assert text == "hello from muse spark"
    assert transport.captured["url"] == "https://example.test/v1/chat/completions"
    assert transport.captured["headers"]["Authorization"] == "Bearer secret-key"
    assert transport.captured["payload"]["model"] == "muse-spark-xl"


def test_complete_json_parses_object():
    transport = _fake_transport('{"ok": true, "n": 3}')
    client = MetaModelClient(config=load_config({}), transport=transport)

    result = client.complete_json("give me json")

    assert result == {"ok": True, "n": 3}
    assert transport.captured["payload"]["response_format"] == {"type": "json_object"}


def test_complete_json_raises_on_bad_json():
    transport = _fake_transport("not json at all")
    client = MetaModelClient(config=load_config({}), transport=transport)

    try:
        client.complete_json("give me json")
    except MetaModelError:
        return
    raise AssertionError("expected MetaModelError")
