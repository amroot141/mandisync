from datetime import date, datetime, timezone
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from backend_api.app.core.config import settings
from backend_api.app.models.schemas import PredictionRequest, PredictionResponse

logger = logging.getLogger("mandisync.ml_runner")


class MLRunner:
    """
    Thread-safe Singleton service that manages the lifecycle of the trained XGBoost model artifact.
    Loads price_predictor_v1.pkl once into system memory on application startup and serves
    sub-millisecond predictions.
    """
    _instance: Optional["MLRunner"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MLRunner, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.model_data: Optional[Dict[str, Any]] = None
        self.preprocessor: Optional[Any] = None
        self.regressor: Optional[XGBRegressor] = None
        self.model_version: str = "unknown"
        self.metrics: Dict[str, Any] = {}
        self.rmse: float = 60.0  # Default fallback uncertainty band
        self.is_ready: bool = False
        self._initialized = True

    def load_model(self, model_path: Optional[str] = None):
        """
        Securely load the serialized XGBoost model pipeline into memory.
        """
        path = Path(model_path or settings.MODEL_PATH)
        logger.info(f"Loading ML Model artifacts starting from: {path.resolve()}")

        models_dir = path.parent
        if not path.exists():
            # If not found directly, attempt search in parent directories
            fallback_dir = Path(__file__).resolve().parent.parent.parent.parent / "ml_engine" / "models"
            if (fallback_dir / "price_predictor_v1_xgb.json").exists():
                models_dir = fallback_dir

        xgb_model_path = models_dir / "price_predictor_v1_xgb.json"
        preprocessor_path = models_dir / "price_predictor_v1_preprocessor.joblib"
        metadata_path = models_dir / "price_predictor_v1_metadata.joblib"

        if not xgb_model_path.exists() or not preprocessor_path.exists() or not metadata_path.exists():
            logger.error(f"Model artifact files do not exist at {models_dir}!")
            raise FileNotFoundError(f"Model artifacts not found at {models_dir}")

        try:
            self.preprocessor = joblib.load(preprocessor_path)
            self.regressor = XGBRegressor()
            self.regressor.load_model(xgb_model_path)
            self.model_data = joblib.load(metadata_path)
            
            self.model_version = self.model_data.get("version", "price_predictor_v1")
            self.metrics = self.model_data.get("metrics", {})
            self.rmse = float(self.metrics.get("RMSE", 58.69))
            self.is_ready = True
            logger.info(
                f"ML Model '{self.model_version}' successfully loaded into system memory. "
                f"(Trained R2: {self.metrics.get('R2', 'N/A')}, RMSE: Rs. {self.rmse:.2f})"
            )
        except Exception as exc:
            self.is_ready = False
            logger.exception(f"Failed to deserialize ML model artifact: {exc}")
            raise RuntimeError(f"Model loading failure: {exc}") from exc

    def predict(
        self,
        commodity: str,
        market: str,
        target_date: Optional[date] = None,
        modal_price_lag1: Optional[float] = None,
        min_price_lag1: Optional[float] = None,
        arrival_tonnes: Optional[float] = None,
        variety: str = "Standard"
    ) -> PredictionResponse:
        """
        Execute high-performance inference for Mandi peak price forecast.
        """
        if not self.is_ready or self.regressor is None or self.preprocessor is None:
            raise RuntimeError("ML Model is not loaded or ready in memory.")

        start_time = time.perf_counter()

        # Date defaults and calendar signals
        t_date = target_date or date.today()
        day_of_week = t_date.weekday()
        month = t_date.month
        day_of_year = t_date.timetuple().tm_yday

        # Commodity baseline heuristics if lags are not explicitly provided
        commodity_clean = commodity.strip().capitalize()
        market_clean = market.strip().capitalize()

        # Baseline prices based on agricultural index
        defaults = {
            "Onion": {"modal": 2400.0, "min": 2050.0, "arrivals": 1100.0},
            "Tomato": {"modal": 1950.0, "min": 1600.0, "arrivals": 900.0},
            "Potato": {"modal": 1450.0, "min": 1200.0, "arrivals": 1800.0},
            "Wheat": {"modal": 2300.0, "min": 2150.0, "arrivals": 1600.0},
            "Soybean": {"modal": 4650.0, "min": 4300.0, "arrivals": 850.0},
        }
        default_stats = defaults.get(commodity_clean, {"modal": 2000.0, "min": 1700.0, "arrivals": 1000.0})

        m_lag1 = modal_price_lag1 if modal_price_lag1 is not None and modal_price_lag1 > 0 else default_stats["modal"]
        min_lag1 = min_price_lag1 if min_price_lag1 is not None and min_price_lag1 > 0 else default_stats["min"]
        arrivals = arrival_tonnes if arrival_tonnes is not None and arrival_tonnes >= 0 else default_stats["arrivals"]

        # Engineered features matching the trained model pipeline
        price_spread = m_lag1 - min_lag1
        modal_price_7d_mean = m_lag1  # Current best proxy for rolling mean

        input_df = pd.DataFrame([{
            "commodity": commodity_clean,
            "market": market_clean,
            "variety": variety,
            "modal_price_lag1": float(m_lag1),
            "min_price_lag1": float(min_lag1),
            "modal_price_7d_mean": float(modal_price_7d_mean),
            "price_spread": float(price_spread),
            "arrival_tonnes": float(arrivals),
            "day_of_week": int(day_of_week),
            "month": int(month),
            "day_of_year": int(day_of_year)
        }])

        transformed_df = self.preprocessor.transform(input_df)
        raw_pred = self.regressor.predict(transformed_df)[0]
        predicted_max = round(float(raw_pred), 2)

        # 90% Confidence bounds (± 1.645 * RMSE)
        margin = round(1.645 * self.rmse, 2)
        confidence_low = max(0.0, round(predicted_max - margin, 2))
        confidence_high = round(predicted_max + margin, 2)

        # Fair seller floor recommendation: ~92% of predicted max price
        recommended_listing = round(max(min_lag1, predicted_max * 0.92), 2)

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

        return PredictionResponse(
            status="success",
            commodity=commodity_clean,
            market=market_clean,
            target_date=t_date.isoformat(),
            predicted_max_price=predicted_max,
            confidence_interval_low=confidence_low,
            confidence_interval_high=confidence_high,
            recommended_listing_price=recommended_listing,
            model_version=self.model_version,
            inference_latency_ms=latency_ms,
            features_used={
                "modal_price_lag1": m_lag1,
                "min_price_lag1": min_lag1,
                "arrival_tonnes": arrivals,
                "price_spread": round(price_spread, 2),
                "day_of_week": day_of_week,
                "month": month,
                "day_of_year": day_of_year
            },
            timestamp=datetime.now(timezone.utc)
        )


# Global ML Runner Singleton
ml_runner = MLRunner()
