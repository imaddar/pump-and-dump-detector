from scripts.benchmark_integration import summarize_integration_results


def test_summarize_integration_results_aggregates_cache_and_predict_timings():
    summary = summarize_integration_results(
        cache_ready_latencies_ms=[120.0, 140.0, 160.0],
        predict_round_trip_ms=[10.0, 11.0, 12.0],
        predict_api_latency_ms=[7.0, 8.0, 9.0],
    )

    assert summary["cache_ready_ms"]["mean"] == 140.0
    assert summary["cache_ready_ms"]["p95"] == 160.0
    assert summary["predict_round_trip_ms"]["max"] == 12.0
    assert summary["predict_api_latency_ms"]["mean"] == 8.0
