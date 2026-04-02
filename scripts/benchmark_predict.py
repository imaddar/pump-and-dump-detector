import argparse
import statistics
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

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


def build_case_plan(iterations: int, scenario: str) -> list[str]:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if scenario == "warm":
        return ["warm"] * iterations
    if scenario == "cold":
        return ["cold"] * iterations
    if scenario == "mixed-80-20":
        warm_count = round(iterations * 0.8)
        cold_count = iterations - warm_count
        return (["warm"] * warm_count) + (["cold"] * cold_count)
    raise ValueError(f"Unsupported scenario: {scenario}")


def summarize_case_results(
    results: list[dict[str, float | str | dict[str, float]]],
) -> dict[str, dict[str, dict[str, float] | dict[str, float]]]:
    grouped: dict[str, list[dict[str, float | dict[str, float]]]] = {}
    for result in results:
        case = str(result.get("case", "unknown"))
        grouped.setdefault(case, []).append(
            {
                "round_trip_ms": float(result["round_trip_ms"]),
                "api_latency_ms": float(result["api_latency_ms"]),
                "stage_timings_ms": dict(result.get("stage_timings_ms", {})),
            }
        )

    summary = {"all": summarize_latencies(list(grouped.get("warm", [])) + list(grouped.get("cold", [])))} if set(grouped).issubset({"warm", "cold"}) and grouped else {"all": summarize_latencies([{ "round_trip_ms": float(result["round_trip_ms"]), "api_latency_ms": float(result["api_latency_ms"]), "stage_timings_ms": dict(result.get("stage_timings_ms", {})) } for result in results])}
    for case_name, case_results in grouped.items():
        summary[case_name] = summarize_latencies(case_results)
    return summary


def run_benchmark(
    base_url: str,
    symbol: str,
    timestamp: str,
    iterations: int,
    concurrency: int,
) -> list[dict[str, float | dict[str, float]]]:
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")

    def one_request():
        return time_request(base_url, symbol, timestamp)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        return list(executor.map(lambda _: one_request(), range(iterations)))


def run_case_benchmark(
    base_url: str,
    timestamp: str,
    case_plan: list[str],
    concurrency: int,
    symbol_for_case: dict[str, str],
) -> list[dict[str, float | str | dict[str, float]]]:
    if concurrency <= 0:
        raise ValueError("concurrency must be positive")

    def one_request(case: str):
        result = time_request(base_url, symbol_for_case[case], timestamp)
        result["case"] = case
        return result

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        return list(executor.map(one_request, case_plan))


def main():
    parser = argparse.ArgumentParser(description="Benchmark /predict latency.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--time", dest="timestamp", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()

    results = run_benchmark(
        base_url=args.base_url,
        symbol=args.symbol,
        timestamp=args.timestamp,
        iterations=args.iterations,
        concurrency=args.concurrency,
    )
    summary = summarize_latencies(results)

    print(f"iterations={args.iterations}")
    print(f"concurrency={args.concurrency}")
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
