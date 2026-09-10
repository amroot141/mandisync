import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

# Setup repository paths
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml_engine.data_ingestion import fetch_agmarknet_data_from_mongo, engineer_timeseries_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml_engine.train_xgboost")

CATEGORICAL_FEATURES = ["commodity", "market", "variety"]
NUMERICAL_FEATURES = [
    "modal_price_lag1",
    "min_price_lag1",
    "modal_price_7d_mean",
    "price_spread",
    "arrival_tonnes",
    "day_of_week",
    "month",
    "day_of_year"
]
TARGET_FEATURE = "max_price"


def build_pipeline() -> Pipeline:
    """Construct an end-to-end scikit-learn pipeline with preprocessing and XGBoost regressor."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline([
                    ("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
                    ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                CATEGORICAL_FEATURES
            ),
            (
                "num",
                Pipeline([
                    ("impute", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                ]),
                NUMERICAL_FEATURES
            )
        ],
        remainder="drop"
    )

    regressor = XGBRegressor(
        n_estimators=350,
        learning_rate=0.03,
        max_depth=5,
        subsample=0.85,
        colsample_bytree=0.85,
        gamma=0.1,
        reg_alpha=0.5,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor)
        ]
    )
    return pipeline


def evaluate_model(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate key regression evaluation metrics."""
    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_true, y_pred)
    # Guard against division-by-zero when any actual price is 0
    nonzero_mask = y_true != 0
    if nonzero_mask.sum() > 0:
        mape = np.mean(np.abs((y_true[nonzero_mask] - y_pred[nonzero_mask]) / y_true[nonzero_mask])) * 100.0
    else:
        mape = float("nan")

    metrics = {
        "MAE": round(float(mae), 2),
        "RMSE": round(float(rmse), 2),
        "R2": round(float(r2), 4),
        "MAPE_percent": round(float(mape), 2) if not np.isnan(mape) else None
    }
    return metrics


async def train_and_serialize():
    logger.info("Step 1: Fetching Agmarknet historical records...")
    df_raw = await fetch_agmarknet_data_from_mongo()
    
    logger.info("Step 2: Engineering time-series lag and calendar features...")
    df = engineer_timeseries_features(df_raw)

    # Chronological Time-Series Train/Validation Split (80% Train, 20% Test)
    df = df.sort_values(by="arrival_date").reset_index(drop=True)
    split_idx = int(len(df) * 0.80)

    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    logger.info(
        f"Temporal Split: Train rows = {len(train_df)} ({train_df['arrival_date'].min().date()} to {train_df['arrival_date'].max().date()}), "
        f"Test rows = {len(test_df)} ({test_df['arrival_date'].min().date()} to {test_df['arrival_date'].max().date()})"
    )

    features = CATEGORICAL_FEATURES + NUMERICAL_FEATURES
    X_train = train_df[features]
    y_train = train_df[TARGET_FEATURE].values
    X_test = test_df[features]
    y_test = test_df[TARGET_FEATURE].values

    logger.info("Step 3: Training XGBoost Time-Series Regressor...")
    pipeline = build_pipeline()

    # --- Defensive pre-fit guard -----------------------------------------
    # If any NaN or inf slipped through sanitization, abort with diagnostics
    # rather than letting XGBoost raise an opaque C++ error.
    nan_rows = np.isnan(y_train).sum()
    inf_rows = np.isinf(y_train).sum()
    if nan_rows or inf_rows:
        raise ValueError(
            f"Target column '{TARGET_FEATURE}' still contains {nan_rows} NaN and "
            f"{inf_rows} inf values after sanitization. "
            "Check data_ingestion.engineer_timeseries_features()."
        )
    # -------------------------------------------------------------------------

    pipeline.fit(X_train, y_train)

    logger.info("Step 4: Evaluating Model on Out-of-Time Test Set...")
    y_pred = pipeline.predict(X_test)
    metrics = evaluate_model(y_test, y_pred)

    print("\n" + "=" * 50)
    print("      MANDISYNC AI - MODEL PERFORMANCE REPORT")
    print("=" * 50)
    print(f"Target: Predicting Mandi Peak Price ('{TARGET_FEATURE}')")
    print(f"Algorithm: XGBoost Regressor (350 estimators, max_depth=5)")
    print(f"Validation R² Score:              {metrics['R2']:.4f}")
    print(f"Validation RMSE:                  Rs. {metrics['RMSE']:.2f} / Quintal")
    print(f"Validation MAE:                   Rs. {metrics['MAE']:.2f} / Quintal")
    print(f"Mean Absolute Percentage Error:   {metrics['MAPE_percent']:.2f} %")
    print("=" * 50 + "\n")

    # Step 5: Serialize Model Artifact
    models_dir = REPO_ROOT / "ml_engine" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    xgb_model_path = models_dir / "price_predictor_v1_xgb.json"
    pipeline.named_steps["regressor"].save_model(xgb_model_path)
    
    preprocessor_path = models_dir / "price_predictor_v1_preprocessor.joblib"
    joblib.dump(pipeline.named_steps["preprocessor"], preprocessor_path)

    metadata_path = models_dir / "price_predictor_v1_metadata.joblib"
    payload = {
        "categorical_features": CATEGORICAL_FEATURES,
        "numerical_features": NUMERICAL_FEATURES,
        "target_feature": TARGET_FEATURE,
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "version": "price_predictor_v1"
    }
    joblib.dump(payload, metadata_path)
    logger.info(f"Model successfully serialized to: {models_dir}")

    # Verify reload
    loaded_preprocessor = joblib.load(preprocessor_path)
    loaded_model = XGBRegressor()
    loaded_model.load_model(xgb_model_path)

    test_sample = X_test.iloc[0:1]
    X_test_transformed = loaded_preprocessor.transform(test_sample)
    test_prediction = loaded_model.predict(X_test_transformed)[0]
    actual = y_test[0]
    logger.info(
        f"Verification Test Prediction for {test_sample['commodity'].values[0]} at {test_sample['market'].values[0]}: "
        f"Predicted Rs. {test_prediction:.2f} (Actual: Rs. {actual:.2f})"
    )
    return str(xgb_model_path)


if __name__ == "__main__":
    asyncio.run(train_and_serialize())
