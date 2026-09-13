from __future__ import annotations

from typing import Any

import pytest

from app import queues

TOPIC = queues.GREETINGS_TOPIC
CONSUMER = queues.GREETINGS_CONSUMER


def event(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "specversion": "1.0",
        "type": queues.CALLBACK_EVENT_TYPE,
        "source": f"/topic/{TOPIC}/consumer/{CONSUMER}",
        "data": {"messageId": "abc", "queueName": TOPIC, "consumerGroup": CONSUMER},
    }
    base.update(overrides)
    return base


def test_accepts_matching_envelope() -> None:
    assert queues.callback_message_id(event(), TOPIC, CONSUMER) == "abc"


@pytest.mark.parametrize(
    "bad",
    [
        event(type="com.example.evil"),
        event(source="/topic/other/consumer/other"),
        event(data={"messageId": "abc", "queueName": "other", "consumerGroup": CONSUMER}),
    ],
)
def test_rejects_foreign_envelope(bad: dict[str, Any]) -> None:
    with pytest.raises((ValueError, KeyError, TypeError)):
        queues.callback_message_id(bad, TOPIC, CONSUMER)


def test_receipt_handles_stay_one_path_segment() -> None:
    assert queues._segment("abc/def?x#y") == "abc%2Fdef%3Fx%23y"
