"""
Synthetic transaction data generator for fraud detection training & simulation.
Generates realistic credit card transactions with fraudulent patterns.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import uuid
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.config import data_config


MERCHANT_CATEGORIES = [
    "grocery", "gas_station", "restaurant", "online_retail", "electronics",
    "travel", "entertainment", "healthcare", "clothing", "jewelry",
    "crypto_exchange", "wire_transfer", "atm_withdrawal", "gambling"
]

HIGH_RISK_CATEGORIES = {"crypto_exchange", "wire_transfer", "gambling", "jewelry"}

COUNTRIES = {
    "US": 0.60, "UK": 0.08, "CA": 0.06, "AU": 0.04, "DE": 0.04,
    "FR": 0.03, "IN": 0.03, "CN": 0.02, "BR": 0.02, "RU": 0.02,
    "NG": 0.01, "RO": 0.01, "UA": 0.01, "VN": 0.01, "XX": 0.02,
}

HIGH_RISK_COUNTRIES = {"RU", "NG", "UA", "XX", "RO", "VN"}


def generate_transaction_id() -> str:
    return str(uuid.uuid4())


def _weighted_choice(choices: dict) -> str:
    keys = list(choices.keys())
    weights = list(choices.values())
    return random.choices(keys, weights=weights, k=1)[0]


def generate_legitimate_transaction(user_id: int, base_time: datetime) -> dict:
    """Generate a realistic legitimate transaction."""
    category = _weighted_choice({
        "grocery": 0.25, "gas_station": 0.15, "restaurant": 0.20,
        "online_retail": 0.15, "electronics": 0.05, "travel": 0.05,
        "entertainment": 0.05, "healthcare": 0.05, "clothing": 0.05,
    })

    amount_ranges = {
        "grocery": (10, 200), "gas_station": (20, 80), "restaurant": (8, 120),
        "online_retail": (5, 500), "electronics": (50, 800), "travel": (100, 1500),
        "entertainment": (10, 100), "healthcare": (20, 300), "clothing": (20, 400),
    }
    lo, hi = amount_ranges.get(category, (10, 500))
    amount = round(np.random.lognormal(mean=np.log((lo + hi) / 2), sigma=0.4), 2)
    amount = max(lo, min(hi * 1.5, amount))

    hour = int(np.random.choice(range(24), p=_hour_distribution()))
    txn_time = base_time + timedelta(hours=hour, minutes=random.randint(0, 59))

    country = _weighted_choice(COUNTRIES)

    return {
        "transaction_id": generate_transaction_id(),
        "user_id": f"USER_{user_id:05d}",
        "timestamp": txn_time.isoformat(),
        "amount": amount,
        "merchant_category": category,
        "country": country,
        "is_high_risk_country": int(country in HIGH_RISK_COUNTRIES),
        "is_high_risk_category": int(category in HIGH_RISK_CATEGORIES),
        "hour_of_day": hour,
        "day_of_week": txn_time.weekday(),
        "is_weekend": int(txn_time.weekday() >= 5),
        "is_night": int(hour < 6 or hour > 22),
        "distance_from_home_km": round(np.random.exponential(15), 1),
        "velocity_1h": random.randint(1, 3),
        "velocity_24h": random.randint(1, 8),
        "failed_attempts_24h": 0,
        "card_present": random.choices([1, 0], weights=[0.6, 0.4])[0],
        "is_international": int(country != "US"),
        "amount_vs_avg_ratio": round(np.random.normal(1.0, 0.3), 3),
        "is_fraud": 0,
    }


def generate_fraudulent_transaction(user_id: int, base_time: datetime) -> dict:
    """Generate a transaction with fraud patterns."""
    fraud_type = random.choice([
        "card_not_present", "account_takeover", "high_velocity",
        "unusual_location", "large_amount", "after_hours"
    ])

    txn = generate_legitimate_transaction(user_id, base_time)

    if fraud_type == "card_not_present":
        txn["card_present"] = 0
        txn["merchant_category"] = random.choice(["online_retail", "electronics", "crypto_exchange"])
        txn["amount"] = round(random.uniform(200, 2000), 2)
        txn["failed_attempts_24h"] = random.randint(2, 8)

    elif fraud_type == "account_takeover":
        txn["country"] = random.choice(list(HIGH_RISK_COUNTRIES))
        txn["is_high_risk_country"] = 1
        txn["is_international"] = 1
        txn["distance_from_home_km"] = round(random.uniform(500, 5000), 1)
        txn["amount"] = round(random.uniform(500, 5000), 2)
        txn["failed_attempts_24h"] = random.randint(1, 5)

    elif fraud_type == "high_velocity":
        txn["velocity_1h"] = random.randint(8, 25)
        txn["velocity_24h"] = random.randint(15, 60)
        txn["amount"] = round(random.uniform(50, 500), 2)
        txn["failed_attempts_24h"] = random.randint(0, 3)

    elif fraud_type == "unusual_location":
        txn["country"] = random.choice(list(HIGH_RISK_COUNTRIES))
        txn["is_high_risk_country"] = 1
        txn["distance_from_home_km"] = round(random.uniform(200, 8000), 1)
        txn["is_international"] = 1

    elif fraud_type == "large_amount":
        txn["amount"] = round(random.uniform(2000, 15000), 2)
        txn["merchant_category"] = random.choice(["jewelry", "wire_transfer", "crypto_exchange"])
        txn["is_high_risk_category"] = 1
        txn["amount_vs_avg_ratio"] = round(random.uniform(5, 30), 3)

    elif fraud_type == "after_hours":
        txn["hour_of_day"] = random.choice([1, 2, 3, 4])
        txn["is_night"] = 1
        txn["amount"] = round(random.uniform(300, 3000), 2)
        txn["velocity_1h"] = random.randint(3, 10)

    txn["is_fraud"] = 1
    return txn


def _hour_distribution():
    """Realistic hour-of-day distribution (peaks at lunch & evening)."""
    weights = [
        0.005, 0.003, 0.002, 0.002, 0.003, 0.008,   # 0-5 AM
        0.020, 0.035, 0.045, 0.050, 0.055, 0.060,   # 6-11 AM
        0.065, 0.060, 0.055, 0.050, 0.055, 0.065,   # 12-17 PM
        0.075, 0.075, 0.065, 0.050, 0.035, 0.012,   # 18-23 PM
    ]
    total = sum(weights)
    return [w / total for w in weights]


def generate_dataset(
    n_samples: int = None,
    fraud_ratio: float = None,
    random_state: int = None,
) -> pd.DataFrame:
    """
    Generate a labeled synthetic fraud dataset.

    Returns:
        pd.DataFrame with transactions and 'is_fraud' label.
    """
    n_samples = n_samples or data_config.n_samples
    fraud_ratio = fraud_ratio or data_config.fraud_ratio
    random_state = random_state or data_config.random_state

    random.seed(random_state)
    np.random.seed(random_state)

    n_fraud = int(n_samples * fraud_ratio)
    n_legit = n_samples - n_fraud

    n_users = max(500, n_samples // 20)
    base_time = datetime(2024, 1, 1)
    records = []

    print(f"[DataGenerator] Generating {n_legit:,} legitimate transactions...")
    for _ in range(n_legit):
        uid = random.randint(1, n_users)
        day_offset = random.randint(0, 364)
        txn = generate_legitimate_transaction(uid, base_time + timedelta(days=day_offset))
        records.append(txn)

    print(f"[DataGenerator] Generating {n_fraud:,} fraudulent transactions...")
    for _ in range(n_fraud):
        uid = random.randint(1, n_users)
        day_offset = random.randint(0, 364)
        txn = generate_fraudulent_transaction(uid, base_time + timedelta(days=day_offset))
        records.append(txn)

    df = pd.DataFrame(records)
    df = df.sample(frac=1, random_state=random_state).reset_index(drop=True)

    print(f"[DataGenerator] Done. Total={len(df):,} | Fraud={df['is_fraud'].sum():,} ({df['is_fraud'].mean()*100:.2f}%)")
    return df


def generate_realtime_transaction() -> dict:
    """
    Generate a single random transaction for real-time streaming simulation.
    ~5% fraud rate for demo visibility.
    """
    is_fraud = random.random() < 0.05
    user_id = random.randint(1, 10000)
    base_time = datetime.now()

    if is_fraud:
        return generate_fraudulent_transaction(user_id, base_time)
    else:
        return generate_legitimate_transaction(user_id, base_time)


if __name__ == "__main__":
    df = generate_dataset(n_samples=1000)
    print(df.head())
    print(df["is_fraud"].value_counts())
