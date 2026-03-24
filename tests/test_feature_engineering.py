from tests.mock_feature_engineering_data import (
    MOCK_BASELINE_CANDLES,
    MOCK_BINANCE_EVENT,
    MOCK_PUMP_CANDLES,
)
import pandas as pd
import pytest
from pandas import DatetimeTZDtype
from features.feature_engineering import (
    FEATURE_COLUMNS,
    compute_features,
    parse_klines,
)


def test_parse_klines_builds_expected_numeric_and_derived_columns() -> None:
    parsed = parse_klines(MOCK_PUMP_CANDLES)
    assert list(parsed["open_time"]) == sorted(parsed["open_time"].tolist())
    assert isinstance(parsed["open_time"].dtype, DatetimeTZDtype)
    assert pd.api.types.is_float_dtype(parsed["open"])
    assert pd.api.types.is_float_dtype(parsed["close"])
    assert pd.api.types.is_float_dtype(parsed["volume"])
    assert pd.api.types.is_float_dtype(parsed["num_trades"])
    first_candle = parsed.iloc[0]
    peak_candle = parsed.iloc[3]
    assert first_candle["candle_range"] == pytest.approx(0.00001020 - 0.00000990)
    assert first_candle["taker_buy_ratio"] == pytest.approx(72.0 / 120.0)
    assert peak_candle["candle_range"] == pytest.approx(0.00001150 - 0.00001070)
    assert peak_candle["taker_buy_ratio"] == pytest.approx(740.0 / 860.0)


def test_compute_features_returns_model_feature_set_in_expected_order() -> None:
    features = compute_features(MOCK_PUMP_CANDLES, MOCK_BASELINE_CANDLES)
    assert list(features.keys()) == FEATURE_COLUMNS
    assert len(features) == len(FEATURE_COLUMNS)
    assert all(isinstance(value, float) for value in features.values())


def test_compute_features_matches_mock_event_calculations() -> None:
    event_features = compute_features(
        MOCK_BINANCE_EVENT["candles"],
        MOCK_BINANCE_EVENT["baseline"],
    )
    expected = {
        "price_change_max": 0.1186943620178042,
        "taker_buy_ratio_peak": 0.8604651162790697,
        "vol_burst_max": 860.0,
        "trade_count_max": 155.0,
        "price_acceleration": 0.072844968862668,
        "baseline_volume_mean": 52.666666666666664,
        "baseline_volume_std": 8.041558721209878,
        "baseline_trade_count_mean": 10.5,
        "baseline_trade_count_std": 1.8708286933869707,
        "baseline_candle_range_mean": 4.4999999999999993e-07,
        "baseline_candle_range_std": 5.4772255750516396e-08,
        "vol_zscore_peak": 100.39512988943468,
        "vol_ratio_vs_7d": 16.329113920950167,
        "trade_count_zscore": 77.23849849983351,
        "range_expansion_ratio": 1.7391304347826106,
    }
    for feature_name, expected_value in expected.items():
        assert event_features[feature_name] == pytest.approx(expected_value)
    assert event_features["vol_burst_max"] > event_features["baseline_volume_mean"]
    assert event_features["trade_count_max"] > event_features["baseline_trade_count_mean"]
    assert event_features["range_expansion_ratio"] > 1.0


def test_compute_features_value_constraints() -> None:
    features = compute_features(MOCK_PUMP_CANDLES, MOCK_BASELINE_CANDLES)
    assert 0.0 <= features["taker_buy_ratio_peak"] <= 1.0
    assert features["baseline_volume_mean"] > 0.0
    assert features["baseline_volume_std"] >= 0.0