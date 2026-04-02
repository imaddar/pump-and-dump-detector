import argparse
import statistics
import time
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from service.app import app
from service.binance import BinanceConnectionError
from tests.mock_feature_engineering_data import MOCK_BASELINE_CANDLES, MOCK_PUMP_CANDLES


def summarize_degraded_results(results: list[dict]) -> dict:
    latencies = [float(result["latency_ms"]) for result in results]
    status_counts: dict[int, int] = {}
    for result in results:
        status_counts[result["status_code"]] = status_counts.get(result["status_code"], 0) + 1
    return {
        "request_count": len(results),
        "error_rate": sum(not result["ok"] for result in results) / len(results),
        "status_counts": status_counts,
        "latency_ms": {
            "mean": statistics.mean(latencies),
            "max": max(latencies),
        },
    }


def run_degraded_benchmark(iterations: int, delay_seconds: float, fail: bool) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    def delayed_resolve_symbol(symbol: str):
        time.sleep(delay_seconds)
        return "MOCKBTC"

    def delayed_get_pump_data(symbol: str, pump_time):
        time.sleep(delay_seconds)
        if fail:
            raise BinanceConnectionError("Injected degraded pump failure")
        return MOCK_PUMP_CANDLES, pump_time, pump_time

    def delayed_get_baseline_data(symbol: str, pump_time):
        time.sleep(delay_seconds)
        return MOCK_BASELINE_CANDLES

    results = []
    with TestClient(app) as client, patch("service.app.resolve_symbol", side_effect=delayed_resolve_symbol), patch(
        "service.app.check_redis_symbol", return_value=False
    ), patch("service.app.get_pump_data", side_effect=delayed_get_pump_data), patch(
        "service.app.get_baseline_data", side_effect=delayed_get_baseline_data
    ):
        for _ in range(iterations):
            start = time.perf_counter()
            response = client.post("/predict", json={"symbol": "MOCK", "time": now})
            results.append(
                {
                    "ok": response.status_code == 200,
                    "latency_ms": (time.perf_counter() - start) * 1000,
                    "status_code": response.status_code,
                }
            )
    return summarize_degraded_results(results)


def main():
    parser = argparse.ArgumentParser(description="Benchmark degraded dependency behavior for /predict.")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--delay-ms", type=float, default=200.0)
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args()

    summary = run_degraded_benchmark(
        iterations=args.iterations,
        delay_seconds=args.delay_ms / 1000,
        fail=args.fail,
    )
    print(summary)


if __name__ == "__main__":
    main()
