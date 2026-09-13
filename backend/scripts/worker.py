"""Poll-mode Vercel Queues worker, for local development.

In production the `greetings` topic is consumed by the push callback configured in
vercel.json; this script exercises the same topic from a laptop after `vercel env pull`.
"""

from __future__ import annotations

import asyncio

from app import queues
from app.telemetry import emit

CONSUMER = "greetings-local"


async def main() -> None:
    while True:
        messages = await queues.receive(queues.GREETINGS_TOPIC, CONSUMER)
        for message in messages:
            emit(
                "info",
                "queue.consumed",
                consumer=CONSUMER,
                messageId=message["messageId"],
                payload=message["payload"],
            )
            await queues.acknowledge(
                queues.GREETINGS_TOPIC, CONSUMER, message["receiptHandle"]
            )
        if not messages:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
