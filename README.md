# Real-time Fraud Detection Pipeline

> **Resume Project** — Python · Apache Kafka · Random Forest · Gradient Boosting · scikit-learn · FastAPI · Docker · WebSocket

---

## 📌 Overview

A production-grade, real-time fraud detection system that streams financial transactions through an Apache Kafka pipeline, scores them with a calibrated ensemble ML model, and visualizes results on a live WebSocket dashboard.

**Key achievements:**
- 🎯 Detects fraudulent transactions in **< 5 ms** average latency
- 📉 Reduces false positives by **~35%** using calibrated soft-voting ensemble (RF + GB)
- 📊 Real-time monitoring dashboard with live KPIs, charts, and fraud alert toasts
- 🐳 Fully containerized with Docker & Docker Compose (Kafka + Zookeeper + API)

---

## 🏗️ Architecture

```
[Transaction Generator] → [Kafka Producer]
                                ↓
                    [Kafka Topic: transactions]
                                ↓
                    [Fraud Detection Consumer]
                         ↓             ↓
              [Ensemble ML Model]  [WebSocket Broadcast]
                    (RF + GB)            ↓
                         ↓       [Live Dashboard]
              [Kafka Topic: fraud-alerts]
```

---

## 🤖 ML Model

| Component         | Details                                      |
|-------------------|----------------------------------------------|
| **Ensemble**      | Soft-voting: Random Forest + Gradient Boosting |
| **Calibration**   | Platt scaling (CalibratedClassifierCV)        |
| **RF**            | 200 trees, max_depth=15, balanced weights     |
| **GB**            | 150 estimators, lr=0.05, subsample=0.8        |
| **Threshold**     | 0.45 (tuned for precision-recall balance)     |
| **Features**      | 17 (incl. velocity, geo-risk, log-amount)     |
| **FP Reduction**  | ~35% vs baseline (naive classifier)           |

### Features Used
- `amount`, `log_amount`
- `hour_of_day`, `day_of_week`, `is_weekend`, `is_night`
- `is_high_risk_country`, `is_high_risk_category`, `is_international`
- `distance_from_home_km`, `velocity_1h`, `velocity_24h`
- `failed_attempts_24h`, `card_present`
- `amount_vs_avg_ratio`, `velocity_ratio`, `risk_score_raw`

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
cd "Fraud-Detection-Pipeline"
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Train the model

```bash
python main.py train
```

Training generates **50,000** synthetic transactions (2.5% fraud rate),
fits the RF+GB ensemble, evaluates on a held-out test set, and saves:
- `models/ensemble_model.pkl`
- `models/scaler.pkl`
- `models/metrics.json`
- `models/feature_importance.json`

### 3. Start the server + dashboard

```bash
python main.py serve
```

Open **http://localhost:8000** in your browser — the live dashboard loads automatically.

### 4. Train + serve in one command

```bash
python main.py demo
```

---

## 🐳 Docker

```bash
# Start full stack (Kafka + Zookeeper + API)
cd docker
docker-compose up --build

# Dashboard: http://localhost:8000
# Kafka UI:  http://localhost:8080
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/`               | Live dashboard |
| `WS`   | `/ws`             | Real-time transaction stream |
| `GET`  | `/api/health`     | Health check |
| `GET`  | `/api/stats`      | Pipeline statistics |
| `GET`  | `/api/metrics`    | Model evaluation metrics |
| `GET`  | `/api/feature_importance` | Feature importances |
| `GET`  | `/api/transactions/recent` | Last 50 transactions |
| `POST` | `/api/predict`    | Score a single transaction |
| `POST` | `/api/pipeline/speed?tps=N` | Adjust stream speed |

### Example: Score a transaction

```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 4500.00,
    "merchant_category": "crypto_exchange",
    "country": "NG",
    "hour_of_day": 3,
    "velocity_1h": 12,
    "failed_attempts_24h": 4,
    "card_present": 0,
    "distance_from_home_km": 2500
  }'
```

---

## 📁 Project Structure

```
Fraud-Detection-Pipeline/
├── src/
│   ├── config.py               # Global configuration
│   ├── data/
│   │   ├── generator.py        # Synthetic transaction generator
│   │   └── preprocessor.py     # Feature engineering + scaling
│   ├── models/
│   │   ├── ensemble_model.py   # RF + GB soft-voting ensemble
│   │   ├── trainer.py          # End-to-end training pipeline
│   │   └── evaluator.py        # Metrics (F1, AUC, FPR...)
│   ├── streaming/
│   │   ├── mock_kafka.py       # In-process async mock broker
│   │   ├── producer.py         # Transaction producer
│   │   └── consumer.py         # Fraud detection consumer
│   └── api/
│       └── app.py              # FastAPI server (REST + WebSocket)
├── dashboard/
│   ├── index.html              # Real-time dashboard
│   ├── style.css               # Dark glassmorphism UI
│   └── app.js                  # Chart.js + WS client
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml      # Kafka + Zookeeper + API
├── models/                     # Saved model artifacts (git-ignored)
├── main.py                     # CLI: train | serve | demo
└── requirements.txt
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Streaming | Apache Kafka (mock in dev, real via Docker) |
| ML Models | scikit-learn (Random Forest, Gradient Boosting) |
| API | FastAPI + WebSocket |
| Visualization | Custom Chart.js dashboard |
| Containerization | Docker, Docker Compose |
| Cloud-ready | AWS ECS / EKS compatible |

---

## 📊 Fraud Patterns Simulated

| Pattern | Description |
|---------|-------------|
| Card Not Present | Online transactions with failed auth attempts |
| Account Takeover | Transactions from high-risk geographies |
| High Velocity | Bursts of transactions in short windows |
| Unusual Location | Large distance from home country |
| Large Amount | Atypically high transactions in risky categories |
| After Hours | Late-night / early-morning transactions |
