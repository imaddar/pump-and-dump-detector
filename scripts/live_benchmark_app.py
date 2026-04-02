from datetime import datetime, timezone

from service.app import app
from tests.mock_feature_engineering_data import MOCK_BASELINE_CANDLES, MOCK_PUMP_CANDLES
import service.app as service_app


FEATURE_PAYLOAD = {
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


def benchmark_resolve_symbol(symbol: str) -> str:
    return symbol


def benchmark_check_redis_symbol(symbol: str, key_type: str) -> bool:
    return key_type == "pump" and symbol == "MOCKWARM"


def benchmark_get_redis_symbol(symbol: str, key_type: str):
    if key_type == "pump" and symbol == "MOCKWARM":
        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "features": FEATURE_PAYLOAD,
        }
    return None


def benchmark_get_pump_data(symbol: str, pump_time: datetime):
    return MOCK_PUMP_CANDLES, pump_time, pump_time


def benchmark_get_baseline_data(symbol: str, pump_time: datetime):
    return MOCK_BASELINE_CANDLES


service_app.resolve_symbol = benchmark_resolve_symbol
service_app.check_redis_symbol = benchmark_check_redis_symbol
service_app.get_redis_symbol = benchmark_get_redis_symbol
service_app.get_pump_data = benchmark_get_pump_data
service_app.get_baseline_data = benchmark_get_baseline_data

