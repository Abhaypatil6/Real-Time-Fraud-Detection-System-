"""
Fraud detection consumer — reads transactions from Kafka (mock),
runs the ensemble model, publishes results to fraud-alerts topic,
and broadcasts to connected WebSocket clients.
"""
import asyncio
import json
import time
import sys
import os
from typing import Callable, Awaitable

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.config import kafka_config
from src.streaming.mock_kafka import broker as mock_broker


class FraudDetectionConsumer:
    """
    Consumes transactions, scores them with the ensemble model,
    and routes to fraud-alerts or cleared channels.
    """

    def __init__(
        self,
        model=None,
        preprocessor=None,
        ws_broadcast: Callable[..., Awaitable] = None,
    ):
        self.model = model
        self.preprocessor = preprocessor
        self.ws_broadcast = ws_broadcast
        self.input_topic = kafka_config.topic_transactions
        self.alert_topic = kafka_config.topic_fraud_alerts
        self._running = False
        self._stats = {
            "processed": 0,
            "fraud_detected": 0,
            "alerts_sent": 0,
            "avg_latency_ms": 0.0,
            "latency_sum": 0.0,
            "recent_transactions": [],
        }

    async def process_transaction(self, txn: dict) -> dict:
        """Score a single transaction and return enriched result."""
        t0 = time.perf_counter()

        result = txn.copy()

        if self.model and self.preprocessor:
            try:
                X = self.preprocessor.transform_single(txn)
                prediction = self.model.predict_single(X)
                result.update(prediction)
            except Exception as e:
                print(f"[Consumer] Model error: {e}")
                result.update({
                    "fraud_probability": 0.0,
                    "is_fraud": txn.get("is_fraud", 0),
                    "risk_level": "UNKNOWN",
                })
        else:
            # Fallback: use ground-truth label (demo mode)
            prob = 0.85 if txn.get("is_fraud") else round(0.05 + 0.15 * abs(
                txn.get("velocity_1h", 1) - 1) / 25, 3)
            result["fraud_probability"] = min(prob, 0.99)
            result["risk_level"] = self.model._risk_level(prob) if self.model else (
                "HIGH" if txn.get("is_fraud") else "LOW"
            )

        latency_ms = (time.perf_counter() - t0) * 1000
        result["detection_latency_ms"] = round(latency_ms, 2)
        result["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Update stats
        self._stats["processed"] += 1
        self._stats["latency_sum"] += latency_ms
        self._stats["avg_latency_ms"] = round(
            self._stats["latency_sum"] / self._stats["processed"], 2
        )

        is_fraud = result.get("is_fraud", 0)
        if is_fraud:
            self._stats["fraud_detected"] += 1

        # Keep rolling window of last 50 transactions
        window = self._stats["recent_transactions"]
        window.append({
            "transaction_id": result.get("transaction_id", ""),
            "amount": result.get("amount", 0),
            "is_fraud": is_fraud,
            "fraud_probability": result.get("fraud_probability", 0),
            "risk_level": result.get("risk_level", "LOW"),
            "merchant_category": result.get("merchant_category", ""),
            "country": result.get("country", "US"),
            "timestamp": result.get("timestamp", ""),
            "processed_at": result.get("processed_at", ""),
            "detection_latency_ms": result.get("detection_latency_ms", 0),
        })
        if len(window) > 50:
            window.pop(0)

        # Publish fraud alerts
        if is_fraud:
            await mock_broker.publish(self.alert_topic, result)
            self._stats["alerts_sent"] += 1

        # Broadcast to WebSocket clients
        if self.ws_broadcast:
            await self.ws_broadcast(result)

        return result

    async def run(self):
        """Start consuming from the transactions topic."""
        self._running = True
        mock_broker.subscribe(self.input_topic, self.process_transaction)
        print(f"[Consumer] Listening on topic: {self.input_topic}")
        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            print(f"[Consumer] Stopped. Stats: {self._stats}")

    def stop(self):
        self._running = False

    @property
    def stats(self) -> dict:
        base = {k: v for k, v in self._stats.items() if k != "recent_transactions"}
        base["fraud_rate"] = round(
            self._stats["fraud_detected"] / max(self._stats["processed"], 1) * 100, 2
        )
        return base

    @property
    def recent_transactions(self) -> list:
        return list(reversed(self._stats["recent_transactions"]))
