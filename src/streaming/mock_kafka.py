"""
In-process Kafka mock using asyncio queues.
Allows full pipeline testing without a running Kafka broker.
Used by the FastAPI server in development mode.
"""
import asyncio
import json
from collections import defaultdict
from typing import Callable, Awaitable


class MockKafkaBroker:
    """Singleton in-memory pub/sub broker."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._topics: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
            cls._instance._subscribers: dict[str, list[Callable]] = defaultdict(list)
        return cls._instance

    async def publish(self, topic: str, message: dict):
        """Put a message onto a topic queue and notify subscribers."""
        payload = json.dumps(message)
        await self._topics[topic].put(payload)
        for cb in self._subscribers[topic]:
            try:
                await cb(message)
            except Exception as e:
                print(f"[MockKafka] Subscriber error on {topic}: {e}")

    async def consume(self, topic: str) -> dict:
        """Block until a message is available on the topic."""
        raw = await self._topics[topic].get()
        return json.loads(raw)

    def subscribe(self, topic: str, callback: Callable[..., Awaitable]):
        """Register an async callback for a topic (push model)."""
        self._subscribers[topic].append(callback)

    def qsize(self, topic: str) -> int:
        return self._topics[topic].qsize()


# Shared singleton
broker = MockKafkaBroker()
