import argparse
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import redis
import requests
from kafka import KafkaProducer

from scripts.benchmark_predict import percentile


TOPICS = ("baseline_data", "pump_data")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

FAKE_PUMP_DATA = [
    [1711929600000, "1.00", "1.05", "0.99", "1.04", "180.0", 1711929659999, "185.0", 120, "150.0", "155.0", "0"],
    [1711929660000, "1.04", "1.08", "1.03", "1.07", "260.0", 1711929719999, "278.0", 180, "220.0", "235.0", "0"],
]
FAKE_BASELINE_DATA = [
    [1711324800000, "0.95", "0.97", "0.94", "0.96", "40.0", 1711328399999, "38.4", 18, "21.0", "20.1", "0"],
    [1711328400000, "0.96", "0.98", "0.95", "0.97", "42.0", 1711331999999, "40.7", 20, "22.0", "21.3", "0"],
    [1711332000000, "0.97", "0.99", "0.96", "0.98", "39.0", 1711335599999, "38.2", 19, "20.0", "19.6", "0"],
]


def build_symbols(count: int) -> list[str]:
    return [f"INTEG{i:03d}USDT" for i in range(count)]


def summarize_metric(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def summarize_integration_results(
    *,
    cache_ready_latencies_ms: list[float],
    predict_round_trip_ms: list[float],
    predict_api_latency_ms: list[float],
) -> dict[str, dict[str, float]]:
    return {
        "cache_ready_ms": summarize_metric(cache_ready_latencies_ms),
        "predict_round_trip_ms": summarize_metric(predict_round_trip_ms),
        "predict_api_latency_ms": summarize_metric(predict_api_latency_ms),
    }


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda payload: __import__("json").dumps(payload).encode("utf-8"),
    )


def wait_for_redis_key(redis_client: redis.Redis, key: str, timeout_seconds: float) -> float:
    start = time.perf_counter()
    while (time.perf_counter() - start) < timeout_seconds:
        if redis_client.exists(key):
            return (time.perf_counter() - start) * 1000
        time.sleep(0.01)
    raise TimeoutError(f"Timed out waiting for Redis key {key}")


def publish_baseline_snapshot(producer: KafkaProducer, symbol: str, timestamp: str) -> None:
    producer.send(
        TOPICS[0],
        {"symbol": symbol, "fetched_at": timestamp, "data": FAKE_BASELINE_DATA},
    )


def publish_pump_snapshot(producer: KafkaProducer, symbol: str, timestamp: str) -> None:
    producer.send(
        TOPICS[1],
        {"symbol": symbol, "fetched_at": timestamp, "data": FAKE_PUMP_DATA},
    )


def benchmark_predict(base_url: str, symbols: list[str], concurrency: int) -> tuple[list[float], list[float]]:
    timestamp = datetime.now(timezone.utc).isoformat()

    def one_request(symbol: str):
        start = time.perf_counter()
        response = requests.post(
            f"{base_url}/predict",
            json={"symbol": symbol, "time": timestamp},
            timeout=30,
        )
        response.raise_for_status()
        round_trip_ms = (time.perf_counter() - start) * 1000
        payload = response.json()
        return round_trip_ms, float(payload["latency_ms"])

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(one_request, symbols))
    return [result[0] for result in results], [result[1] for result in results]


def run_integration_benchmark(
    *,
    symbol_count: int,
    base_url: str,
    predict_concurrency: int,
    redis_timeout_seconds: float,
) -> dict[str, dict[str, float]]:
    timestamp = datetime.now(timezone.utc).isoformat()
    symbols = build_symbols(symbol_count)
    producer = create_producer()
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    cache_ready_latencies_ms: list[float] = []
    try:
        for symbol in symbols:
            redis_client.delete(f"baseline:{symbol}", f"pump:{symbol}")
            publish_baseline_snapshot(producer, symbol, timestamp)
        producer.flush()

        for symbol in symbols:
            wait_for_redis_key(redis_client, f"baseline:{symbol}", redis_timeout_seconds)

        publish_start = time.perf_counter()
        for symbol in symbols:
            publish_pump_snapshot(producer, symbol, timestamp)
        producer.flush()

        for symbol in symbols:
            cache_ready_latencies_ms.append(
                ((time.perf_counter() - publish_start) * 1000)
                + wait_for_redis_key(redis_client, f"pump:{symbol}", redis_timeout_seconds)
            )

        predict_round_trip_ms, predict_api_latency_ms = benchmark_predict(
            base_url=base_url,
            symbols=symbols,
            concurrency=predict_concurrency,
        )
    finally:
        producer.close()

    return summarize_integration_results(
        cache_ready_latencies_ms=cache_ready_latencies_ms,
        predict_round_trip_ms=predict_round_trip_ms,
        predict_api_latency_ms=predict_api_latency_ms,
    )


def main():
    parser = argparse.ArgumentParser(description="Benchmark real Kafka->Redis->API integration.")
    parser.add_argument("--symbol-count", type=int, default=25)
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--predict-concurrency", type=int, default=10)
    parser.add_argument("--redis-timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    summary = run_integration_benchmark(
        symbol_count=args.symbol_count,
        base_url=args.base_url,
        predict_concurrency=args.predict_concurrency,
        redis_timeout_seconds=args.redis_timeout_seconds,
    )
    print(summary)


if __name__ == "__main__":
    main()
