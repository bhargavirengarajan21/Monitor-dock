"""Incident Memory — 2-minute demo narrative (Story 27).

Runs the whole story end to end, offline and deterministic, so it can be filmed
or shown live with no accounts, keys, or services:

    python demo.py

Each step prints what a judge needs to see: capture with human approval, recall
with citations, the team permission filter, and an honest no-match.
"""

from __future__ import annotations

from incident_backend.seed import seed_backend
from incident_memory_ai.config import load_config
from incident_memory_ai.meta_client import MetaModelClient


def _offline_meta_client(config):
    """A Muse Spark stand-in: writes the cited answer from the evidence, no key."""

    def transport(url, headers, body):
        import json

        prompt = json.loads(body.decode("utf-8"))["messages"][-1]["content"]
        # Pull the first past-incident line and the live count out of the prompt
        # so the printed answer reflects the real retrieved evidence.
        cause = fix = ""
        for line in prompt.splitlines():
            if "cause:" in line and "fix:" in line:
                cause = line.split("cause:", 1)[1].split("fix:", 1)[0].strip()
                fix = line.split("fix:", 1)[1].strip()
                break
        text = (
            f"Past cause: {cause} [1] The fix that worked: {fix} [1] "
            "See the current error count in the monitoring citation [2]."
        )
        return {"choices": [{"message": {"content": text}}]}

    return MetaModelClient(config=config, transport=transport)


def _print_answer(title: str, result: dict) -> None:
    answer = result["answer"]
    print(f"\n=== {title} ===")
    print(f"alert : {result['alert']['error_code']} on {result['alert']['service']}")
    if answer["no_match"]:
        print(f"answer: {answer['text']}  (honest no-match — nothing similar)")
        return
    print(f"answer: {answer['text']}")
    for i, c in enumerate(answer["citations"], 1):
        print(f"  [{i}] {c['kind']:<10} {c['label']}  {c['url']}")


def main() -> None:
    config = load_config({"NO_MATCH_THRESHOLD": "0.55"})
    backend = seed_backend(config=config, meta_client=_offline_meta_client(config))

    print("Incident Memory — demo")
    print("Seeded teams:", [t.team_id for t in backend.registry.teams()])
    print("Approved postmortems in memory:", len(backend.list_incidents("approved")))

    # 1. The same payment alert fires again — recall the past fix.
    nr = {
        "details": {"error_code": "ERR_PAYMENT_409"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
        "incident_url": "https://one.newrelic.com/alerts/payment-409",
    }
    _print_answer("1. Payments alert fires again", backend.ingest_alert("new_relic", nr, "payments"))

    # 2. A different tool (Prometheus), a different team — same recall path.
    prom = {
        "status": "firing",
        "alerts": [{
            "status": "firing",
            "labels": {"service": "checkout-web", "error_code": "ERR_CHECKOUT_503"},
            "startsAt": "2026-11-04T10:00:00Z",
            "generatorURL": "https://prometheus/graph",
        }],
    }
    _print_answer("2. Checkout alert via Prometheus", backend.ingest_alert("prometheus", prom, "web"))

    # 3. Permission filter: the 'web' team fires the payments error — no access.
    web_asks_payments = {
        "details": {"error_code": "ERR_PAYMENT_409"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
    }
    _print_answer(
        "3. Permission filter (web team cannot see payments' postmortem)",
        backend.ingest_alert("new_relic", web_asks_payments, "web"),
    )

    # 4. Honest miss: a never-seen error.
    never = {
        "details": {"error_code": "ERR_NEVER_SEEN_777"},
        "targets": [{"labels": {"service": "payment-service"}}],
        "current_state": "open",
    }
    _print_answer("4. Honest no-match on a new error", backend.ingest_alert("new_relic", never, "payments"))

    # 5. Read-only guardrail.
    print("\n=== 5. Read-only guardrail ===")
    refusal = backend.ask("revert the deploy", team_id="payments")["refusal"]
    print("ask   : 'revert the deploy'")
    print(f"answer: {refusal['message']}")


if __name__ == "__main__":
    main()
