"""In-process event bus — the Kafka stand-in (Stories 15, 17, 18).

The README carries ``postmortem.approved`` and ``document.changed`` on Kafka so
indexing never blocks the user. To keep the backend offline and dependency-free,
this bus delivers the same two topics in process, preserving the two properties
the stories rely on:

* **Idempotent publish** (Story 15): publishing the same topic+key twice emits
  one event, so approving a postmortem twice never creates duplicate work.
* **Decoupled consumers** (Story 17): subscribers (the indexer) run on publish,
  the same way a Kafka consumer would.

A real deployment swaps this for a Kafka producer/consumer with the same keys.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Set, Tuple

# Topic names, matching the README's Kafka topics table.
POSTMORTEM_APPROVED = "postmortem.approved"
DOCUMENT_CHANGED = "document.changed"

Handler = Callable[[dict], None]


class EventBus:
    """Synchronous pub/sub with per-topic idempotency keys."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Handler]] = {}
        self._seen: Set[Tuple[str, str]] = set()

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    def publish(self, topic: str, key: str, payload: dict) -> bool:
        """Deliver an event, skipping duplicates by (topic, key).

        Returns True if this is the first time the key is seen on the topic (and
        the event was delivered), False if it was a duplicate and suppressed.
        """

        if (topic, key) in self._seen:
            return False
        self._seen.add((topic, key))
        for handler in self._subscribers.get(topic, []):
            handler(payload)
        return True
