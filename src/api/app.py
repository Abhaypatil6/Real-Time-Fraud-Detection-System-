"""
FastAPI application — REST + WebSocket backend for the fraud detection dashboard.
"""
import asyncio
import json
import os
import sys
import time
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.config import app_config, model_config
from src.streaming.producer import TransactionProducer
from src.streaming.consumer import FraudDetectionConsumer

# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Real-time Fraud Detection API",
    description="Ensemble ML model (RF + GB) for detecting fraudulent transactions via Kafka streaming",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── State ─────────────────────────────────────────────────────────────
_producer: TransactionProducer = None
_consumer: FraudDetectionConsumer = None
_producer_task: asyncio.Task = None
_consumer_task: asyncio.Task = None
_ws_clients: List[WebSocket] = []
_model = None
_preprocessor = None
_model_loaded = False
_start_time = time.time()


# ── WebSocket broadcast ───────────────────────────────────────────────
async def _broadcast(message: dict):
    """Send scored transaction to all connected WebSocket clients."""
    dead = []
    payload = json.dumps(message)
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# ── Startup / shutdown ────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global _producer, _consumer, _producer_task, _consumer_task
    global _model, _preprocessor, _model_loaded

    # Try loading trained model
    try:
        from src.models.ensemble_model import FraudEnsembleModel
        from src.data.preprocessor import FraudPreprocessor
        _model = FraudEnsembleModel.load(model_config.ensemble_model_path)
        _preprocessor = FraudPreprocessor.load(model_config.scaler_path)
        _model_loaded = True
        print("[API] [OK] Trained model loaded.")
    except Exception as e:
        print(f"[API] [WARN] Model not found ({e}). Running in demo mode.")
        _model_loaded = False

    _consumer = FraudDetectionConsumer(
        model=_model if _model_loaded else None,
        preprocessor=_preprocessor if _model_loaded else None,
        ws_broadcast=_broadcast,
    )
    _producer = TransactionProducer(tps=2.0)

    _consumer_task = asyncio.create_task(_consumer.run())
    _producer_task = asyncio.create_task(_producer.run())
    print("[API] [START] Streaming pipeline started.")


@app.on_event("shutdown")
async def shutdown():
    if _producer:
        _producer.stop()
    if _consumer:
        _consumer.stop()
    if _producer_task:
        _producer_task.cancel()
    if _consumer_task:
        _consumer_task.cancel()


# ── WebSocket endpoint ────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    print(f"[WS] Client connected. Total: {len(_ws_clients)}")
    try:
        while True:
            await ws.receive_text()  # Keep alive
    except WebSocketDisconnect:
        _ws_clients.remove(ws)
        print(f"[WS] Client disconnected. Total: {len(_ws_clients)}")


# ── REST endpoints ────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": _model_loaded,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "ws_clients": len(_ws_clients),
    }


@app.get("/api/stats")
async def get_stats():
    if not _consumer:
        raise HTTPException(status_code=503, detail="Consumer not running")
    return {
        "pipeline": _consumer.stats,
        "producer": _producer.stats if _producer else {},
        "model_loaded": _model_loaded,
    }


@app.get("/api/transactions/recent")
async def recent_transactions(limit: int = 50):
    if not _consumer:
        raise HTTPException(status_code=503, detail="Consumer not running")
    txns = _consumer.recent_transactions[:limit]
    return {"transactions": txns, "count": len(txns)}


@app.get("/api/metrics")
async def get_model_metrics():
    metrics_path = "models/metrics.json"
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            return json.load(f)
    return {"error": "No metrics found. Train the model first."}


@app.get("/api/feature_importance")
async def get_feature_importance():
    path = "models/feature_importance.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


class TransactionIn(BaseModel):
    amount: float
    merchant_category: str = "online_retail"
    country: str = "US"
    hour_of_day: int = 12
    day_of_week: int = 1
    velocity_1h: int = 1
    velocity_24h: int = 3
    failed_attempts_24h: int = 0
    card_present: int = 1
    distance_from_home_km: float = 5.0


@app.post("/api/predict")
async def predict_single(txn: TransactionIn):
    """Score a single transaction via the REST API."""
    if not _model_loaded:
        raise HTTPException(status_code=503, detail="Model not trained yet. Run: python -m src.models.trainer")

    import uuid
    from datetime import datetime

    raw = txn.dict()
    raw.update({
        "transaction_id": str(uuid.uuid4()),
        "user_id": "USER_MANUAL",
        "timestamp": datetime.utcnow().isoformat(),
        "is_weekend": int(raw["day_of_week"] >= 5),
        "is_night": int(raw["hour_of_day"] < 6 or raw["hour_of_day"] > 22),
        "is_high_risk_country": int(raw["country"] in {"RU", "NG", "UA", "XX", "RO", "VN"}),
        "is_high_risk_category": int(raw["merchant_category"] in {
            "crypto_exchange", "wire_transfer", "gambling", "jewelry"
        }),
        "is_international": int(raw["country"] != "US"),
        "amount_vs_avg_ratio": 1.0,
    })

    X = _preprocessor.transform_single(raw)
    result = _model.predict_single(X)
    result["transaction_id"] = raw["transaction_id"]
    result["input"] = txn.dict()
    return result


@app.post("/api/pipeline/speed")
async def set_speed(tps: float = 2.0):
    """Adjust producer TPS (0.5 – 20)."""
    if not _producer:
        raise HTTPException(status_code=503, detail="Producer not running")
    tps = max(0.5, min(20.0, tps))
    _producer.tps = tps
    return {"tps": tps}


# ── Static files (dashboard) ──────────────────────────────────────────
dashboard_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'dashboard')
if os.path.isdir(dashboard_dir):
    app.mount("/static", StaticFiles(directory=dashboard_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(os.path.join(dashboard_dir, "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "Fraud Detection API running. Dashboard not found."}
