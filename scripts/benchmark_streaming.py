import argparse
import time
from datetime import datetime, timezone
from unittest.mock import patch

from streaming.consumer import handle_baseline, handle_pump
from streaming.producer import publish_baseline_snapshots, publish_pump_snapshots


class FakeProducer:
    def __init__(self):
        self.messages: list[tuple[str, dict]] = []

    def send(self, topic: str, payload: dict):
        self.messages.append((topic, payload))


class FakeMessage:
    def __init__(self, topic: str, payload: dict):
        self._topic = topic
        self._payload = payload

    def value(self):
        import json

        return json.dumps(self._payload).encode("utf-8")

    def topic(self):
        return self._topic

    def error(self):
        return None


def summarize_streaming_results(
    *,
    symbol_count: int,
    baseline_publish_ms: float,
    pump_publish_ms: float,
    consumer_process_ms: float,
    end_to_end_ms: float,
) -> dict[str, float]:
    return {
        "symbol_count": symbol_count,
        "baseline_publish_ms": baseline_publish_ms,
        "pump_publish_ms": pump_publish_ms,
        "consumer_process_ms": consumer_process_ms,
        "end_to_end_ms": end_to_end_ms,
        "symbols_per_second": symbol_count / (end_to_end_ms / 1000),
    }


def build_symbols(count: int) -> list[str]:
    return [f"TOKEN{i}USDT" for i in range(count)]


def run_streaming_benchmark(symbol_count: int) -> dict[str, float]:
    symbols = build_symbols(symbol_count)
    producer = FakeProducer()
    baseline_cache: dict[str, list[list]] = {}

    fake_pump_data = [[1, "1", "1", "1", "1", "1", 2, "1", 1, "1", "1", "0"]]
    fake_baseline_data = [[1, "1", "1", "1", "1", "1", 2, "1", 1, "1", "1", "0"]]

    total_start = time.perf_counter()
    with patch("streaming.producer.get_pump_data", return_value=(fake_pump_data, datetime.now(), datetime.now())), patch(
        "streaming.producer.get_baseline_data", return_value=fake_baseline_data
    ):
        start = time.perf_counter()
        publish_baseline_snapshots(producer, symbols)
        baseline_publish_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        publish_pump_snapshots(producer, symbols)
        pump_publish_ms = (time.perf_counter() - start) * 1000

    def fake_set_redis_symbol(symbol: str, data, key_type: str, captured_at=None):
        if key_type == "baseline":
            baseline_cache[symbol] = data

    def fake_check_redis_symbol(symbol: str, key_type: str):
        return symbol in baseline_cache if key_type == "baseline" else False

    def fake_get_redis_symbol(symbol: str, key_type: str):
        if key_type == "baseline":
            return {"data": baseline_cache[symbol], "computed_at": datetime.now(timezone.utc).isoformat()}
        return None

    start = time.perf_counter()
    with patch("streaming.consumer.set_redis_symbol", side_effect=fake_set_redis_symbol), patch(
        "streaming.consumer.check_redis_symbol", side_effect=fake_check_redis_symbol
    ), patch("streaming.consumer.get_redis_symbol", side_effect=fake_get_redis_symbol), patch(
        "streaming.consumer.compute_features", return_value={"price_change_max": 1.0}
    ):
        for topic, payload in producer.messages:
            message = FakeMessage(topic, payload)
            if topic == "baseline_data":
                handle_baseline(message)
            else:
                handle_pump(message)
    consumer_process_ms = (time.perf_counter() - start) * 1000

    return summarize_streaming_results(
        symbol_count=symbol_count,
        baseline_publish_ms=baseline_publish_ms,
        pump_publish_ms=pump_publish_ms,
        consumer_process_ms=consumer_process_ms,
        end_to_end_ms=(time.perf_counter() - total_start) * 1000,
    )


def main():
    parser = argparse.ArgumentParser(description="Benchmark streaming throughput with synthetic watchlists.")
    parser.add_argument("--symbol-counts", nargs="+", type=int, default=[10, 50, 100, 250, 500])
    args = parser.parse_args()

    for symbol_count in args.symbol_counts:
        result = run_streaming_benchmark(symbol_count)
        print(f"symbol_count={symbol_count}")
        for key, value in result.items():
            if key == "symbol_count":
                continue
            print(f"{key}={value:.2f}")


if __name__ == "__main__":
    main()
