import os
from pathlib import Path
from typing import List
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "MandiSync AI"
    DESCRIPTION: str = "Decentralized ONDC Seller Node & Agricultural Price Prediction ML Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # MongoDB Configuration
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb+srv://abhi20singhbhati_db_user:4D6ZmP790VgmSqgX@cluster0.sgu4gdt.mongodb.net/")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "mandisync_db")
    MONGO_TIMEOUT_MS: int = 10000
    
    # Redis Configuration
    REDIS_URI: str = os.getenv("REDIS_URI", "redis://default:4bkabryirVFrFKriMizPVdKwlHYtvwH5@window-megaclear-receipt-44278.db.redis.io:17635")
    
    # Model Artifact Path
    MODEL_PATH: str = os.getenv(
        "MODEL_PATH",
        str(BASE_DIR / "ml_engine" / "models" / "price_predictor_v1_xgb.json")
    )
    
    # ONDC Protocol Configurations
    ONDC_BPP_ID: str = os.getenv("ONDC_BPP_ID", "seller.mandisync.ai")
    ONDC_BPP_URI: str = os.getenv("ONDC_BPP_URI", "http://127.0.0.1:8000/ondc")
    ONDC_DOMAIN: str = "nic2004:52110"  # ONDC Retail: Agriculture Produce
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
