"""Story 15 — the event bus publishes idempotently by key."""

from incident_backend.events import POSTMORTEM_APPROVED, EventBus


def test_publish_delivers_to_subscribers():
    bus = EventBus()
    seen = []
    bus.subscribe(POSTMORTEM_APPROVED, lambda payload: seen.append(payload))

    published = bus.publish(POSTMORTEM_APPROVED, key="inc-1", payload={"incident_id": "inc-1"})

    assert published is True
    assert seen == [{"incident_id": "inc-1"}]


def test_same_key_is_published_only_once():
    bus = EventBus()
    seen = []
    bus.subscribe(POSTMORTEM_APPROVED, lambda payload: seen.append(payload))

    first = bus.publish(POSTMORTEM_APPROVED, key="inc-1", payload={"incident_id": "inc-1"})
    second = bus.publish(POSTMORTEM_APPROVED, key="inc-1", payload={"incident_id": "inc-1"})

    assert first is True
    assert second is False  # duplicate suppressed
    assert len(seen) == 1  # the subscriber ran once
