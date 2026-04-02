import argparse
import statistics
import time
from datetime import datetime, timezone

import requests


def time_request(base_url: str, symbol: str, timestamp: str) -> dict[str, float | dict[str, float]]:
    start = time.perf_counter()
    response = requests.post(
        f"{base_url}/predict",
        json={"symbol": symbol, "time": timestamp},
        timeout=30,
    )
    response.raise_for_status()
    round_trip_ms = (time.perf_counter() - start) * 1000
    payload = response.json()
    return {
        "round_trip_ms": round_trip_ms,
        "api_latency_ms": float(payload["latency_ms"]),
        "stage_timings_ms": {
            key: float(value)
            for key, value in payload.get("stage_timings_ms", {}).items()
        },
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


def summarize_latencies(
    results: list[dict[str, float | dict[str, float]]],
) -> dict[str, dict[str, float] | dict[str, float]]:
    summary: dict[str, dict[str, float] | dict[str, float]] = {}
    for metric_name in ("round_trip_ms", "api_latency_ms"):
        values = [float(result[metric_name]) for result in results]
        summary[metric_name] = {
            "mean": statistics.mean(values),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
            "max": max(values),
        }

    stage_names = sorted(
        {
            stage_name
            for result in results
            for stage_name in result.get("stage_timings_ms", {}).keys()
        }
    )
    summary["stage_timings_ms"] = {
        stage_name: statistics.mean(
            [
                float(result["stage_timings_ms"][stage_name])
                for result in results
                if stage_name in result.get("stage_timings_ms", {})
            ]
        )
        for stage_name in stage_names
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark /predict latency.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--time", dest="timestamp", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()

    results = [
        time_request(args.base_url, args.symbol, args.timestamp)
        for _ in range(args.iterations)
    ]
    summary = summarize_latencies(results)

    print(f"iterations={args.iterations}")
    for metric_name, values in summary.items():
        if metric_name == "stage_timings_ms":
            continue
        print(f"{metric_name}_mean_ms={values['mean']:.2f}")
        print(f"{metric_name}_p50_ms={values['p50']:.2f}")
        print(f"{metric_name}_p95_ms={values['p95']:.2f}")
        print(f"{metric_name}_max_ms={values['max']:.2f}")
    for stage_name, value in summary["stage_timings_ms"].items():
        print(f"stage_{stage_name}_mean_ms={value:.2f}")


if __name__ == "__main__":
    main()
