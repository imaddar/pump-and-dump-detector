from scripts.benchmark_log import render_benchmark_entry


def test_render_benchmark_entry_includes_metadata_and_cases():
    entry = render_benchmark_entry(
        title="Concurrent Live Server",
        metadata={
            "date": "2026-04-02",
            "commit": "abc1234",
            "environment": "local uvicorn",
        },
        cases={
            "warm": {
                "round_trip_ms": {"mean": 1.5, "p50": 1.4, "p95": 2.0, "max": 2.4},
                "api_latency_ms": {"mean": 1.0, "p50": 0.9, "p95": 1.3, "max": 1.5},
                "stage_timings_ms": {"model_predict": 0.6, "total": 1.0},
            }
        },
        notes=["Warm cache stayed under 2 ms p95."],
    )

    assert "## Concurrent Live Server" in entry
    assert "- Commit: `abc1234`" in entry
    assert "### warm" in entry
    assert "- Round-trip mean: 1.50 ms" in entry
    assert "- `model_predict`: 0.60 ms" in entry
    assert "- Warm cache stayed under 2 ms p95." in entry
