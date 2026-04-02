import argparse
import json
import time
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts.benchmark_predict import build_case_plan, summarize_case_results
from service.app import app
from tests.mock_feature_engineering_data import MOCK_BASELINE_CANDLES, MOCK_PUMP_CANDLES


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


def benchmark_scenarios(iterations: int, scenario: str, timestamp: str):
    plan = build_case_plan(iterations=iterations, scenario=scenario)
    results = []
    with TestClient(app) as client:
        for case in plan:
            patches = [
                patch("service.app.resolve_symbol", return_value="MOCKBTC"),
            ]
            if case == "warm":
                patches.extend(
                    [
                        patch("service.app.check_redis_symbol", return_value=True),
                        patch(
                            "service.app.get_redis_symbol",
                            return_value={
                                "computed_at": timestamp,
                                "features": FEATURE_PAYLOAD,
                            },
                        ),
                    ]
                )
            else:
                now = datetime.fromisoformat(timestamp)
                patches.extend(
                    [
                        patch("service.app.check_redis_symbol", return_value=False),
                        patch("service.app.get_pump_data", return_value=(MOCK_PUMP_CANDLES, now, now)),
                        patch("service.app.get_baseline_data", return_value=MOCK_BASELINE_CANDLES),
                    ]
                )

            for active_patch in patches:
                active_patch.start()
            try:
                start = time.perf_counter()
                response = client.post("/predict", json={"symbol": "MOCK", "time": timestamp})
                response.raise_for_status()
                payload = response.json()
                results.append(
                    {
                        "case": case,
                        "round_trip_ms": (time.perf_counter() - start) * 1000,
                        "api_latency_ms": float(payload["latency_ms"]),
                        "stage_timings_ms": {k: float(v) for k, v in payload["stage_timings_ms"].items()},
                    }
                )
            finally:
                for active_patch in reversed(patches):
                    active_patch.stop()
    return summarize_case_results(results)


def main():
    parser = argparse.ArgumentParser(description="Benchmark warm, cold, or mixed /predict scenarios.")
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--scenario", choices=["warm", "cold", "mixed-80-20"], default="mixed-80-20")
    parser.add_argument("--time", dest="timestamp", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()

    print(json.dumps(benchmark_scenarios(args.iterations, args.scenario, args.timestamp), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
