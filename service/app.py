import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, Request, HTTPException

from modeling.shap_analysis import (
    build_tree_explainer,
    compute_shap_values,
    get_top_feature_impacts,
)

from .schemas import PredictRequest, PredictResponse
from .binance import get_pump_data, get_baseline_data, resolve_symbol, BinanceConnectionError, BinanceNoDataError
from features.feature_engineering import compute_features
from streaming.redis_client import check_redis_symbol, get_redis_symbol

CACHE_MAX_AGE = timedelta(hours=2)


@asynccontextmanager
async def lifespan(app):
    # loads in the model and the metadata on startup of the FastAPI server
    model = lgb.Booster(model_file="modeling/models/lgbm_tuned.txt")
    app.state.model = model
    app.state.metadata = json.load(Path("modeling/models/lgbm_tuned.json").open("r"))
    app.state.explainer = build_tree_explainer(model)
    yield
    # everything after the yield happens on shutdown of the server


app = FastAPI(lifespan=lifespan)


def record_stage_timing(stage_timings_ms: dict[str, float], stage_name: str, stage_start: float) -> None:
    stage_timings_ms[stage_name] = (time.perf_counter() - stage_start) * 1000


def get_cached_feature_dict(symbol: str, request_time: datetime) -> dict | None:
    if not check_redis_symbol(symbol, "pump"):
        return None

    cached_payload = get_redis_symbol(symbol, "pump")
    if not cached_payload:
        return None

    if isinstance(cached_payload, dict) and "features" in cached_payload:
        computed_at = datetime.fromisoformat(cached_payload["computed_at"])
        if computed_at.tzinfo is None:
            computed_at = computed_at.replace(tzinfo=timezone.utc)
        if request_time - computed_at > CACHE_MAX_AGE:
            raise HTTPException(status_code=503, detail=f"Cached features for {symbol} are stale")
        return cached_payload["features"]

    return cached_payload

@app.post("/predict")
async def predict(request: Request, body: PredictRequest):
    start = time.perf_counter()
    stage_timings_ms: dict[str, float] = {}
    model = request.app.state.model
    metadata = request.app.state.metadata
    explainer = request.app.state.explainer
    symbol, pump_time = body.symbol, body.time

    stage_start = time.perf_counter()
    try:
        symbol = resolve_symbol(symbol)
    except BinanceNoDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BinanceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    record_stage_timing(stage_timings_ms, "resolve_symbol", stage_start)

    cached_feature_dict = get_cached_feature_dict(symbol, pump_time)
    if cached_feature_dict is not None:
        feature_dict = cached_feature_dict
        window_start = window_end = pump_time
        stage_timings_ms["get_pump_data"] = 0.0
        stage_timings_ms["get_baseline_data"] = 0.0
        stage_timings_ms["compute_features"] = 0.0
    else:
        stage_start = time.perf_counter()
        try:
            pump_data, window_start, window_end = get_pump_data(symbol, pump_time)
        except BinanceConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except BinanceNoDataError as e:
            raise HTTPException(status_code=404, detail=str(e))
        record_stage_timing(stage_timings_ms, "get_pump_data", stage_start)

        stage_start = time.perf_counter()
        try:
            baseline_data = get_baseline_data(symbol, pump_time)
        except BinanceConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except BinanceNoDataError as e:
            raise HTTPException(status_code=404, detail=str(e))
        record_stage_timing(stage_timings_ms, "get_baseline_data", stage_start)

        stage_start = time.perf_counter()
        try:
            feature_dict = compute_features(pump_data, baseline_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Feature computation failed: {str(e)}")
        record_stage_timing(stage_timings_ms, "compute_features", stage_start)

    feature_columns = metadata["feature_columns"]
    stage_start = time.perf_counter()
    try:
        feature_frame = pd.DataFrame([feature_dict], columns=feature_columns)
        risk_score = float(model.predict(feature_frame)[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
    record_stage_timing(stage_timings_ms, "model_predict", stage_start)

    risk_label = "high_risk" if risk_score >= metadata["threshold"] else "low_risk"
    stage_start = time.perf_counter()
    try:
        shap_values, _ = compute_shap_values(explainer, feature_frame)
        top_signals = get_top_feature_impacts(
            shap_values_row=shap_values[0],
            feature_names=feature_columns,
            top_n=3,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SHAP computation failed: {str(e)}")
    record_stage_timing(stage_timings_ms, "compute_shap_values", stage_start)

    latency_ms = (time.perf_counter() - start) * 1000
    stage_timings_ms["total"] = latency_ms
    return PredictResponse(
        risk_label=risk_label,
        risk_score=risk_score,
        top_signals=top_signals,
        computed_at=datetime.now(timezone.utc),
        window_start=window_start,
        window_end=window_end,
        latency_ms=latency_ms,
        stage_timings_ms=stage_timings_ms,
        model_version=metadata['trained_at']
    )

@app.get("/health")
async def health_check(request: Request):
    return {"status": "ok", "model_version": request.app.state.metadata['trained_at']}
    
@app.get("/model/metrics")
async def model_metrics(request: Request):
    return {
        "pr_auc": request.app.state.metadata['pr_auc'],
        "f1_score": request.app.state.metadata['f1'],
        "threshold": request.app.state.metadata['threshold']
    }
