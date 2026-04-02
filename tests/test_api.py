# makes sure endpoints are doing what they are supposed to; returning correct shape + status codes, etc.
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request, HTTPException
from service.app import app
from unittest.mock import patch
from tests.mock_feature_engineering_data import (
    MOCK_BASELINE_CANDLES,
    MOCK_BINANCE_EVENT,
    MOCK_PUMP_CANDLES,
)
from datetime import datetime, timezone



def test_health_check(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "model_version" in response.json()
    
def test_metrics(test_client):
    response = test_client.get("/model/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "pr_auc" in data
    assert "f1_score" in data
    assert "threshold" in data
    assert isinstance(data["pr_auc"], float)
    assert isinstance(data["f1_score"], float)
    assert isinstance(data["threshold"], float)

@patch("service.app.resolve_symbol", return_value="MOCKBTC")
@patch("service.app.get_baseline_data")
@patch("service.app.get_pump_data")
@patch("service.app.check_redis_symbol", return_value=False)
def test_predict(mock_redis, mock_pump, mock_baseline, mock_resolve, test_client):
    now = datetime.now(timezone.utc)
    mock_pump.return_value = (MOCK_PUMP_CANDLES, now, now)
    mock_baseline.return_value = MOCK_BASELINE_CANDLES
    
    response = test_client.post("/predict", json={"symbol": "MOCK", "time": now.isoformat()})
    assert response.status_code == 200
    data = response.json()
    assert "risk_label" in data
    assert "risk_score" in data
    assert "top_signals" in data
    assert "computed_at" in data
    assert "window_start" in data
    assert "window_end" in data
    assert "latency_ms" in data
    assert "stage_timings_ms" in data
    assert "model_version" in data
    assert "resolve_symbol" in data["stage_timings_ms"]
    assert "get_pump_data" in data["stage_timings_ms"]
    assert "get_baseline_data" in data["stage_timings_ms"]
    assert "compute_features" in data["stage_timings_ms"]
    assert "model_predict" in data["stage_timings_ms"]
    assert "compute_shap_values" in data["stage_timings_ms"]
    assert "total" in data["stage_timings_ms"]
    
def test_predict_missing_symbol(test_client):
    now = datetime.now(timezone.utc)
    response = test_client.post("/predict", json={"time": now.isoformat()})
    assert response.status_code == 422

def test_predict_invalid_time(test_client):
    response = test_client.post("/predict", json={"symbol": "MOCK", "time": "not-a-time"})
    assert response.status_code == 422


@patch("service.app.resolve_symbol", return_value="MOCKBTC")
@patch("service.app.get_baseline_data")
@patch("service.app.get_pump_data")
@patch("service.app.check_redis_symbol", return_value=False)
@patch("service.app.compute_shap_values")
def test_predict_can_skip_shap(
    mock_compute_shap,
    mock_redis,
    mock_pump,
    mock_baseline,
    mock_resolve,
    test_client,
):
    now = datetime.now(timezone.utc)
    mock_pump.return_value = (MOCK_PUMP_CANDLES, now, now)
    mock_baseline.return_value = MOCK_BASELINE_CANDLES

    response = test_client.post(
        "/predict",
        json={"symbol": "MOCK", "time": now.isoformat(), "include_explanations": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["top_signals"] == []
    assert data["stage_timings_ms"]["compute_shap_values"] == 0.0
    mock_compute_shap.assert_not_called()
