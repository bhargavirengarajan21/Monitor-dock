"""Stories 25 & 36 — the demo seeder and team tool registry."""

from incident_backend.registry import TeamRegistry
from incident_backend.seed import build_registry, load_dataset, seed_backend
from incident_memory_ai.config import load_config
from incident_memory_ai.meta_client import MetaModelClient


def _meta_client():
    def transport(url, headers, body):
        return {"choices": [{"message": {"content": "answer [1] [2]"}}]}

    return MetaModelClient(config=load_config({}), transport=transport)


def test_registry_builds_permission_policy_from_visibility():
    registry = TeamRegistry()
    registry.register("payments", "new_relic", [])
    registry.register("platform", "new_relic", ["payments"])

    policy = registry.permission_policy()

    assert policy.allowed_teams("payments") == {"payments"}
    assert policy.allowed_teams("platform") == {"platform", "payments"}
    assert registry.tool_for("payments") == "new_relic"


def test_bundled_dataset_loads_and_registers_teams():
    dataset = load_dataset()
    registry = build_registry(dataset)

    team_ids = {t.team_id for t in registry.teams()}
    assert {"payments", "web"} <= team_ids


def test_seed_backend_approves_and_indexes_every_incident():
    backend = seed_backend(meta_client=_meta_client())

    approved = backend.list_incidents("approved")
    assert len(approved) >= 3
    # All approved incidents produced searchable chunks.
    assert backend.store.all_chunks()


def test_seeded_backend_recalls_a_known_incident():
    backend = seed_backend(meta_client=_meta_client())

    result = backend.ingest_alert(
        "new_relic",
        {
            "details": {"error_code": "ERR_PAYMENT_409"},
            "targets": [{"labels": {"service": "payment-service"}}],
            "current_state": "open",
        },
        team_id="payments",
    )

    assert result["answer"]["no_match"] is False


def test_seeded_backend_enforces_permissions_across_teams():
    backend = seed_backend(meta_client=_meta_client())

    # The web team fires the payments error — it must not recall payments' fix.
    result = backend.ingest_alert(
        "new_relic",
        {
            "details": {"error_code": "ERR_PAYMENT_409"},
            "targets": [{"labels": {"service": "payment-service"}}],
            "current_state": "open",
        },
        team_id="web",
    )

    assert result["answer"]["no_match"] is True
