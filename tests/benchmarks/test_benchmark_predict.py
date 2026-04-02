from unittest.mock import Mock, patch

from scripts.benchmark_predict import (
    build_case_plan,
    summarize_case_results,
    summarize_latencies,
    time_request,
)


def test_time_request_returns_round_trip_and_api_latency():
    response = Mock()
    response.json.return_value = {
        "latency_ms": 42.5,
        "stage_timings_ms": {"resolve_symbol": 3.0, "total": 42.5},
    }
    response.raise_for_status.return_value = None

    with patch("scripts.benchmark_predict.requests.post", return_value=response), patch(
        "scripts.benchmark_predict.time.perf_counter",
        side_effect=[100.0, 100.125],
    ):
        result = time_request(
            base_url="http://127.0.0.1:8000",
            symbol="BTC",
            timestamp="2026-01-01T00:00:00+00:00",
        )

    assert result["round_trip_ms"] == 125.0
    assert result["api_latency_ms"] == 42.5
    assert result["stage_timings_ms"]["resolve_symbol"] == 3.0


def test_summarize_latencies_returns_both_views():
    summary = summarize_latencies(
        [
            {"round_trip_ms": 100.0, "api_latency_ms": 60.0},
            {"round_trip_ms": 120.0, "api_latency_ms": 75.0},
            {"round_trip_ms": 140.0, "api_latency_ms": 90.0},
        ]
    )

    assert summary["round_trip_ms"]["mean"] == 120.0
    assert summary["api_latency_ms"]["mean"] == 75.0
    assert summary["round_trip_ms"]["p50"] == 120.0
    assert summary["api_latency_ms"]["max"] == 90.0


def test_summarize_latencies_includes_average_stage_timings():
    summary = summarize_latencies(
        [
            {
                "round_trip_ms": 100.0,
                "api_latency_ms": 60.0,
                "stage_timings_ms": {"resolve_symbol": 10.0, "total": 60.0},
            },
            {
                "round_trip_ms": 120.0,
                "api_latency_ms": 70.0,
                "stage_timings_ms": {"resolve_symbol": 20.0, "total": 70.0},
            },
        ]
    )

    assert summary["stage_timings_ms"]["resolve_symbol"] == 15.0
    assert summary["stage_timings_ms"]["total"] == 65.0


def test_build_case_plan_supports_mixed_traffic():
    plan = build_case_plan(iterations=10, scenario="mixed-80-20")

    assert len(plan) == 10
    assert plan.count("warm") == 8
    assert plan.count("cold") == 2


def test_summarize_case_results_groups_by_case():
    summary = summarize_case_results(
        [
            {"case": "warm", "round_trip_ms": 1.0, "api_latency_ms": 0.8, "stage_timings_ms": {}},
            {"case": "warm", "round_trip_ms": 2.0, "api_latency_ms": 1.2, "stage_timings_ms": {}},
            {"case": "cold", "round_trip_ms": 5.0, "api_latency_ms": 4.2, "stage_timings_ms": {}},
        ]
    )

    assert summary["all"]["round_trip_ms"]["mean"] == 8.0 / 3.0
    assert summary["warm"]["round_trip_ms"]["mean"] == 1.5
    assert summary["cold"]["api_latency_ms"]["mean"] == 4.2
