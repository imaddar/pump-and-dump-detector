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



client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "model_version" in response.json()
    
def test_metrics():
    response = client.get("/model/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "pr_auc" in data
    assert "f1_score" in data
    assert "threshold" in data
    assert isinstance(data["pr_auc"], float)
    assert isinstance(data["f1_score"], float)
    assert isinstance(data["threshold"], float)
    
@patch("service.binance.get_pump_data")
@patch("service.binance.get_baseline_data")
def test_predict(mock_baseline, mock_pump):
    now = datetime.now(timezone.utc)
    mock_pump.return_value = (MOCK_PUMP_CANDLES, now, now)
    mock_baseline.return_value = MOCK_BASELINE_CANDLES
    