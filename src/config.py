"""
Configuration settings for the Fraud Detection Pipeline.
"""
import os
from dataclasses import dataclass

@dataclass
class KafkaConfig:
    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic_transactions: str = "transactions"
    topic_fraud_alerts: str = "fraud-alerts"
    consumer_group: str = "fraud-detection-group"

@dataclass
class ModelConfig:
    model_dir: str = "models"
    ensemble_model_path: str = "models/ensemble_model.pkl"
    scaler_path: str = "models/scaler.pkl"
    rf_n_estimators: int = 200
    rf_max_depth: int = 15
    gb_n_estimators: int = 150
    gb_learning_rate: float = 0.05
    fraud_threshold: float = 0.45  # Lower threshold = more sensitive
    test_size: float = 0.2
    random_state: int = 42

@dataclass
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = True
    cors_origins: list = None

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]

@dataclass
class DataConfig:
    n_samples: int = 50_000
    fraud_ratio: float = 0.025  # 2.5% fraud rate (realistic)
    random_state: int = 42

kafka_config = KafkaConfig()
model_config = ModelConfig()
app_config = AppConfig()
data_config = DataConfig()
