"""Story 40 — read-only assistant refuses actions."""

from incident_memory_ai.guardrails import ReadOnlyGuard
from incident_memory_ai.citations import Citation


def test_detects_action_requests():
    guard = ReadOnlyGuard()
    assert guard.is_action_request("revert the deploy")
    assert guard.is_action_request("please restart the service")
    assert guard.is_action_request("roll back payment-service")


def test_allows_questions():
    guard = ReadOnlyGuard()
    assert not guard.is_action_request("why is ERR_PAYMENT_409 firing?")
    assert not guard.is_action_request("what fixed this last time?")


def test_refusal_explains_read_only_and_includes_links():
    guard = ReadOnlyGuard()
    pointers = [Citation(kind="runbook", label="Payment runbook", url="https://notion/runbook")]
    refusal = guard.refuse("revert the deploy", pointers)
    assert "read-only" in refusal.message.lower()
    assert refusal.links[0].url == "https://notion/runbook"


def test_refusal_without_pointers_still_clear():
    guard = ReadOnlyGuard()
    refusal = guard.refuse("restart the service")
    assert "read-only" in refusal.message.lower()
    assert refusal.links == []
