import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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

@app.post("/predict")
async def predict(request: Request, body: PredictRequest):
    start = time.time()
    model = request.app.state.model
    metadata = request.app.state.metadata
    explainer = request.app.state.explainer
    symbol, pump_time = body.symbol, body.time

    try:
        symbol = resolve_symbol(symbol)
    except BinanceNoDataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BinanceConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if check_redis_symbol(symbol, "pump"):
        feature_dict = get_redis_symbol(symbol, "pump")
        window_start = window_end = pump_time
    else:
        try:
            pump_data, window_start, window_end = get_pump_data(symbol, pump_time)
        except BinanceConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except BinanceNoDataError as e:
            raise HTTPException(status_code=404, detail=str(e))
        try:
            baseline_data = get_baseline_data(symbol, pump_time)
        except BinanceConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except BinanceNoDataError as e:
            raise HTTPException(status_code=404, detail=str(e))
        try:
            feature_dict = compute_features(pump_data, baseline_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Feature computation failed: {str(e)}")

    feature_columns = metadata["feature_columns"]
    try:
        feature_frame = pd.DataFrame([feature_dict], columns=feature_columns)
        risk_score = float(model.predict(feature_frame)[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    risk_label = "high_risk" if risk_score >= metadata["threshold"] else "low_risk"
    try:
        shap_values, _ = compute_shap_values(explainer, feature_frame)
        top_signals = get_top_feature_impacts(
            shap_values_row=shap_values[0],
            feature_names=feature_columns,
            top_n=3,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SHAP computation failed: {str(e)}")

    latency_ms = (time.time() - start) * 1000
    return PredictResponse(
        risk_label=risk_label,
        risk_score=risk_score,
        top_signals=top_signals,
        computed_at=datetime.now(timezone.utc),
        window_start=window_start,
        window_end=window_end,
        latency_ms=latency_ms,
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