from scripts.benchmark_degraded import summarize_degraded_results


def test_summarize_degraded_results_tracks_error_rate():
    summary = summarize_degraded_results(
        [
            {"ok": True, "latency_ms": 100.0, "status_code": 200},
            {"ok": False, "latency_ms": 250.0, "status_code": 503},
            {"ok": False, "latency_ms": 300.0, "status_code": 503},
        ]
    )

    assert summary["request_count"] == 3
    assert summary["error_rate"] == 2 / 3
    assert summary["status_counts"][503] == 2
    assert summary["latency_ms"]["max"] == 300.0
