"""
Transaction producer — publishes synthetic transactions to Kafka (or mock).
Simulates a real payment network sending events.
"""
import asyncio
import json
import random
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.data.generator import generate_realtime_transaction
from src.config import kafka_config
from src.streaming.mock_kafka import broker as mock_broker


class TransactionProducer:
    """
    Async producer that emits synthetic transactions.
    Uses mock Kafka internally; swap for `kafka-python` / `confluent-kafka`
    by replacing the `_send` method with a real producer call.
    """

    def __init__(self, topic: str = None, tps: float = 2.0):
        """
        Args:
            topic: Kafka topic name
            tps:   Transactions per second to produce
        """
        self.topic = topic or kafka_config.topic_transactions
        self.tps = tps
        self._running = False
        self._sent_count = 0
        self._fraud_count = 0

    async def _send(self, message: dict):
        await mock_broker.publish(self.topic, message)

    async def produce_one(self) -> dict:
        """Produce a single transaction and return it."""
        txn = generate_realtime_transaction()
        await self._send(txn)
        self._sent_count += 1
        if txn.get("is_fraud"):
            self._fraud_count += 1
        return txn

    async def run(self, max_count: int = None):
        """
        Continuously produce transactions at `tps` rate.
        Stops after max_count messages if provided, else runs forever.
        """
        self._running = True
        interval = 1.0 / self.tps
        count = 0
        print(f"[Producer] Starting — topic={self.topic}, rate={self.tps} TPS")
        try:
            while self._running:
                if max_count and count >= max_count:
                    break
                txn = await self.produce_one()
                count += 1
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        finally:
            print(f"[Producer] Stopped. Sent={self._sent_count}, Fraud={self._fraud_count}")

    def stop(self):
        self._running = False

    @property
    def stats(self) -> dict:
        return {
            "sent": self._sent_count,
            "fraud_generated": self._fraud_count,
            "fraud_rate": round(self._fraud_count / max(self._sent_count, 1), 4),
        }


if __name__ == "__main__":
    async def _main():
        p = TransactionProducer(tps=5.0)
        await p.run(max_count=20)
        print(p.stats)

    asyncio.run(_main())
