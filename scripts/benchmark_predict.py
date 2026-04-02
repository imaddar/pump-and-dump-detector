import argparse
import statistics
import time
from datetime import datetime, timezone

import requests


def time_request(base_url: str, symbol: str, timestamp: str) -> float:
    start = time.perf_counter()
    response = requests.post(
        f"{base_url}/predict",
        json={"symbol": symbol, "time": timestamp},
        timeout=30,
    )
    response.raise_for_status()
    return (time.perf_counter() - start) * 1000


def percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


def main():
    parser = argparse.ArgumentParser(description="Benchmark /predict latency.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--time", dest="timestamp", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()

    latencies = [
        time_request(args.base_url, args.symbol, args.timestamp)
        for _ in range(args.iterations)
    ]
    print(f"iterations={args.iterations}")
    print(f"mean_ms={statistics.mean(latencies):.2f}")
    print(f"p50_ms={percentile(latencies, 50):.2f}")
    print(f"p95_ms={percentile(latencies, 95):.2f}")
    print(f"max_ms={max(latencies):.2f}")


if __name__ == "__main__":
    main()
