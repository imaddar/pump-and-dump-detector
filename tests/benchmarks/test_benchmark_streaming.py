from scripts.benchmark_streaming import summarize_streaming_results


def test_summarize_streaming_results_computes_throughput():
    summary = summarize_streaming_results(
        symbol_count=20,
        baseline_publish_ms=40.0,
        pump_publish_ms=60.0,
        consumer_process_ms=100.0,
        end_to_end_ms=180.0,
    )

    assert summary["symbol_count"] == 20
    assert summary["symbols_per_second"] == 20 / 0.18
    assert summary["consumer_process_ms"] == 100.0
