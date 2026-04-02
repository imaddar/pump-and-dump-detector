# Benchmarks

## 2026-04-02 Timing Pass

This benchmark pass was run after adding stage-level timing instrumentation to the `/predict` endpoint and updating the benchmark utilities to capture both round-trip latency and API-reported latency.

### Method

- Environment: local `FastAPI` app exercised through `TestClient`
- Iterations per case: 25
- Benchmark date: 2026-04-02
- Data source for performance runs: mocked market data from the test fixtures
- Purpose: isolate application latency from live Binance network noise

### Cases

#### Cold Cache

Definition:
Redis cache miss, so the request goes through symbol resolution, pump fetch, baseline fetch, feature computation, model prediction, and SHAP explanation.

Results:

- Round-trip mean: 8.02 ms
- Round-trip p50: 6.04 ms
- Round-trip p95: 11.54 ms
- Round-trip max: 43.76 ms
- API latency mean: 7.06 ms
- API latency p50: 5.16 ms
- API latency p95: 9.45 ms
- API latency max: 42.42 ms

Average stage timings:

- `resolve_symbol`: 0.02 ms
- `get_pump_data`: 0.01 ms
- `get_baseline_data`: 0.01 ms
- `compute_features`: 5.99 ms
- `model_predict`: 0.59 ms
- `compute_shap_values`: 0.43 ms
- `total`: 7.06 ms

#### Warm Cache

Definition:
Redis cache hit with fresh cached features, so the request skips pump fetch, baseline fetch, and feature computation.

Results:

- Round-trip mean: 1.45 ms
- Round-trip p50: 1.47 ms
- Round-trip p95: 1.70 ms
- Round-trip max: 2.04 ms
- API latency mean: 0.85 ms
- API latency p50: 0.85 ms
- API latency p95: 1.17 ms
- API latency max: 1.30 ms

Average stage timings:

- `resolve_symbol`: 0.01 ms
- `get_pump_data`: 0.00 ms
- `get_baseline_data`: 0.00 ms
- `compute_features`: 0.00 ms
- `model_predict`: 0.51 ms
- `compute_shap_values`: 0.30 ms
- `total`: 0.85 ms

### Takeaways

- The warm-cache path is about 5.5x faster than the cold-cache path by mean round-trip latency.
- In the cold-cache path, feature computation is the main cost center by a wide margin.
- Even with cached features, model prediction and SHAP still account for most of the remaining endpoint time.

### Notes

- These numbers are useful for architecture-level comparison, not for production SLA claims.
- Because external Binance calls were mocked, the fetch stages here represent application overhead only, not internet latency.
- The current SHAP dependency emits a known warning during repeated runs; that warning did not block the benchmark.
