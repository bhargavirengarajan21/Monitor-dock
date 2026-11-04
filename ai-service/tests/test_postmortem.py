"""Story 12 — Muse Spark drafts a postmortem from the evidence."""

from incident_memory_ai.meta_client import MetaModelClient
from incident_memory_ai.postmortem import Evidence, PostmortemDrafter, PostmortemError
from incident_memory_ai.config import load_config

VALID = {
    "title": "Payment 409 after idempotency change",
    "cause": "Deploy abc123 made the idempotency key non-unique.",
    "fix": "Reverted the key change in PR #42.",
    "owner": "jordan",
    "error_codes": ["ERR_PAYMENT_409"],
    "sources": [{"label": "PR #42", "url": "https://github.com/x/y/pull/42"}],
}


def _client_returning(*contents):
    contents = list(contents)

    def transport(url, headers, body):
        content = contents.pop(0)
        return {"choices": [{"message": {"content": content}}]}

    return MetaModelClient(config=load_config({}), transport=transport)


EVIDENCE = Evidence(
    new_relic_error="ERR_PAYMENT_409 spiking on payment-service",
    deploy="deploy abc123 via GitHub Actions run 99",
    fix_pr="PR #42 revert idempotency key",
)


def test_draft_returns_structured_json():
    import json
    client = _client_returning(json.dumps(VALID))
    drafter = PostmortemDrafter(client)
    draft = drafter.draft(EVIDENCE)
    assert draft["title"] == VALID["title"]
    assert draft["error_codes"] == ["ERR_PAYMENT_409"]
    assert draft["sources"][0]["url"].startswith("https://")
    assert draft["status"] == "draft"


def test_invalid_json_is_retried_once_then_succeeds():
    import json
    client = _client_returning("not json", json.dumps(VALID))
    drafter = PostmortemDrafter(client)
    draft = drafter.draft(EVIDENCE)
    assert draft["title"] == VALID["title"]


def test_invalid_twice_is_flagged():
    client = _client_returning("nope", "still nope")
    drafter = PostmortemDrafter(client)
    try:
        drafter.draft(EVIDENCE)
    except PostmortemError:
        return
    raise AssertionError("expected PostmortemError after retry")


def test_missing_required_field_is_flagged():
    import json
    incomplete = dict(VALID)
    del incomplete["sources"]
    client = _client_returning(json.dumps(incomplete), json.dumps(incomplete))
    drafter = PostmortemDrafter(client)
    try:
        drafter.draft(EVIDENCE)
    except PostmortemError as exc:
        assert "sources" in str(exc)
        return
    raise AssertionError("expected PostmortemError for missing sources")
