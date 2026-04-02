# Benchmarks

## 2026-04-02 Post-Optimization Pass

This pass was run after four concrete speedups:

- direct numeric feature computation replaced the pandas-heavy cold inference path
- SHAP explanations became optional on `/predict`
- the consumer now defers pump payloads until baseline data arrives instead of dropping them
- the producer now fetches snapshots concurrently and keys Kafka messages by symbol

### Controlled Endpoint Results

Environment:
`FastAPI TestClient` with mocked market data so the comparison isolates application changes rather than external network noise.

#### Cold Cache With Explanations

- API latency mean: 1.25 ms
- API latency p50: 0.85 ms
- API latency p95: 2.40 ms
- Round-trip mean: 1.96 ms
- Round-trip p50: 1.45 ms
- Round-trip p95: 3.46 ms
- `compute_features` mean: 0.02 ms
- `compute_shap_values` mean: 0.38 ms

Compared with the earlier cold baseline:

- cold API latency improved from 7.06 ms to 1.25 ms
- cold round-trip improved from 8.02 ms to 1.96 ms
- `compute_features` dropped from 5.99 ms to 0.02 ms

#### Cold Cache Without Explanations

- API latency mean: 0.60 ms
- API latency p50: 0.53 ms
- API latency p95: 0.90 ms
- Round-trip mean: 1.15 ms
- Round-trip p50: 1.04 ms
- Round-trip p95: 1.82 ms
- `compute_shap_values`: 0.00 ms

#### Warm Cache With Explanations

- API latency mean: 1.03 ms
- API latency p50: 0.98 ms
- API latency p95: 1.46 ms
- Round-trip mean: 1.72 ms
- Round-trip p50: 1.66 ms
- Round-trip p95: 2.45 ms

#### Warm Cache Without Explanations

- API latency mean: 0.53 ms
- API latency p50: 0.49 ms
- API latency p95: 0.80 ms
- Round-trip mean: 1.03 ms
- Round-trip p50: 1.04 ms
- Round-trip p95: 1.45 ms

### Live Redis and Kafka Follow-Up

Environment:
`docker compose` Redis + Kafka + Zookeeper, host-side `streaming.consumer`, host-side `uvicorn`, and interleaved baseline/pump publishing through real Kafka topics.

#### Interleaved Kafka Publish to Warm Redis Cache

- Symbols: 25
- Publish flush time: 264.01 ms
- Post-flush until all `pump:*` keys were ready: 85.60 ms
- Total until all `pump:*` keys were ready: 349.61 ms

This is the key correctness improvement. Earlier live runs could fail because pump messages arrived before baseline messages and were skipped. After the deferred replay change, all warm pump cache entries were populated successfully under interleaved live traffic.

#### Live Warm `/predict` After Cache Fill

With explanations:

- Warm round-trip mean: 38.11 ms
- Warm API latency mean: 2.93 ms

Without explanations:

- Warm round-trip mean: 14.40 ms
- Warm API latency mean: 1.16 ms

Compared with the earlier 25-symbol live infra run:

- warm round-trip improved from 49.37 ms to 38.11 ms with explanations enabled
- warm API latency improved from 4.11 ms to 2.93 ms with explanations enabled

### Post-Optimization Takeaways

- The biggest measured win came from replacing pandas-based cold-path feature computation.
- Optional SHAP is a strong latency lever and cuts warm and cold API latency by roughly half.
- The live Kafka/Redis path is now materially more reliable because pump messages are deferred and replayed instead of being lost when baseline arrives later.
- The producer is now structured for better throughput via concurrent fetches and symbol-keyed Kafka messages, though the clearest measured gains in this pass were from cold-path compute reduction and SHAP skipping.

## 2026-04-02 Live Infra Pass

These are the highest-signal benchmark results in the repo right now because they use real Docker-backed Redis and Kafka, a real host-side consumer process, and a real uvicorn API server. This is the benchmark slice that best represents production-style system behavior.

### Method

- Environment: `docker compose` Redis + Kafka + Zookeeper, host-side `streaming.consumer`, host-side `uvicorn`
- API app: [`scripts/live_integration_benchmark_app.py`](/Users/imaddar/git-repos/pump-and-dump-detector/scripts/live_integration_benchmark_app.py)
- Benchmark driver: [`scripts/benchmark_integration.py`](/Users/imaddar/git-repos/pump-and-dump-detector/scripts/benchmark_integration.py)
- Benchmark date: 2026-04-02
- Commit baseline: `763ef85`
- Notes:
- Kafka and Redis were live.
- Binance was still mocked so the benchmark isolated queue/cache/inference behavior rather than internet latency.
- Warm `/predict` requests were served through real Redis-backed cache entries populated by the live consumer.

### 25 Symbols

Command:
`uv run python -m scripts.benchmark_integration --symbol-count 25 --base-url http://127.0.0.1:8002 --predict-concurrency 10 --redis-timeout-seconds 20`

Results:

- Cache-ready mean: 208.22 ms
- Cache-ready p50: 206.57 ms
- Cache-ready p95: 266.98 ms
- Cache-ready max: 267.39 ms
- Warm `/predict` round-trip mean: 49.37 ms
- Warm `/predict` round-trip p50: 40.35 ms
- Warm `/predict` round-trip p95: 82.94 ms
- Warm `/predict` round-trip max: 86.18 ms
- Warm `/predict` API latency mean: 4.11 ms
- Warm `/predict` API latency p50: 2.48 ms
- Warm `/predict` API latency p95: 16.04 ms
- Warm `/predict` API latency max: 21.82 ms

### 100 Symbols

Command:
`uv run python -m scripts.benchmark_integration --symbol-count 100 --base-url http://127.0.0.1:8002 --predict-concurrency 20 --redis-timeout-seconds 20`

Results:

- Cache-ready mean: 292.76 ms
- Cache-ready p50: 295.52 ms
- Cache-ready p95: 547.95 ms
- Cache-ready max: 581.23 ms
- Warm `/predict` round-trip mean: 65.24 ms
- Warm `/predict` round-trip p50: 67.77 ms
- Warm `/predict` round-trip p95: 86.77 ms
- Warm `/predict` round-trip max: 90.94 ms
- Warm `/predict` API latency mean: 2.97 ms
- Warm `/predict` API latency p50: 2.32 ms
- Warm `/predict` API latency p95: 7.18 ms
- Warm `/predict` API latency max: 10.22 ms

### Live Infra Takeaways

- The live Kafka-to-Redis path was able to populate warm pump cache entries in roughly 0.2 to 0.3 seconds on average for these controlled payloads.
- The API itself remained relatively cheap once the cache was warm; most of the wall-clock cost in the live benchmark came from HTTP/process/concurrency overhead, not model execution.
- Scaling from 25 to 100 symbols increased cache-ready p95 noticeably, which suggests queueing and consumer-side serial processing are the first real bottlenecks to watch.
- The first attempt at this benchmark failed because pump messages were consumed before baseline messages for the same symbol, causing feature computation to be skipped. That is a real architectural race in the current streaming design, not a benchmark artifact.

### Why This Section Matters More

- These numbers include real broker and cache behavior.
- They test the actual reason the streaming subsystem exists.
- They are the benchmark results that would matter most in an engineering review or hiring conversation.

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

## Concurrent Live Server

- Date: `2026-04-02`
- Commit: `763ef85`
- Environment: `local uvicorn on http://127.0.0.1:8001 using scripts.live_benchmark_app:app`
- Command: `uv run python -m scripts.benchmark_predict_live --base-url http://127.0.0.1:8001 --iterations 50 --concurrency 10 --scenario mixed-80-20`

### all

- Round-trip mean: 35.11 ms
- Round-trip p50: 16.77 ms
- Round-trip p95: 86.30 ms
- Round-trip max: 89.24 ms
- API latency mean: 2.40 ms
- API latency p50: 0.93 ms
- API latency p95: 7.88 ms
- API latency max: 17.73 ms
- Average stage timings:
- `compute_features`: 1.02 ms
- `compute_shap_values`: 0.49 ms
- `get_baseline_data`: 0.00 ms
- `get_pump_data`: 0.00 ms
- `model_predict`: 0.86 ms
- `resolve_symbol`: 0.00 ms
- `total`: 2.40 ms

### warm

- Round-trip mean: 32.18 ms
- Round-trip p50: 16.36 ms
- Round-trip p95: 86.30 ms
- Round-trip max: 89.24 ms
- API latency mean: 1.49 ms
- API latency p50: 0.91 ms
- API latency p95: 2.41 ms
- API latency max: 17.73 ms
- Average stage timings:
- `compute_features`: 0.00 ms
- `compute_shap_values`: 0.52 ms
- `get_baseline_data`: 0.00 ms
- `get_pump_data`: 0.00 ms
- `model_predict`: 0.95 ms
- `resolve_symbol`: 0.00 ms
- `total`: 1.49 ms

### cold

- Round-trip mean: 46.83 ms
- Round-trip p50: 44.36 ms
- Round-trip p95: 67.68 ms
- Round-trip max: 67.68 ms
- API latency mean: 6.02 ms
- API latency p50: 5.18 ms
- API latency p95: 13.07 ms
- API latency max: 13.07 ms
- Average stage timings:
- `compute_features`: 5.10 ms
- `compute_shap_values`: 0.40 ms
- `get_baseline_data`: 0.00 ms
- `get_pump_data`: 0.00 ms
- `model_predict`: 0.51 ms
- `resolve_symbol`: 0.00 ms
- `total`: 6.02 ms

### Notes

- This run used a real HTTP server stack, but benchmark-only mock market data via [`scripts/live_benchmark_app.py`](/Users/imaddar/git-repos/pump-and-dump-detector/scripts/live_benchmark_app.py) to avoid internet noise.
- The gap between API latency and round-trip latency shows the real cost of the live HTTP path and thread contention under concurrency.

## Controlled Mixed Scenario

- Date: `2026-04-02`
- Commit: `763ef85`
- Environment: `FastAPI TestClient with mocked market data`
- Command: `uv run python -m scripts.benchmark_predict_scenarios --iterations 25 --scenario mixed-80-20`

### all

- Round-trip mean: 2.77 ms
- Round-trip p50: 1.79 ms
- Round-trip p95: 6.24 ms
- Round-trip max: 6.69 ms
- API latency mean: 2.01 ms
- API latency p50: 1.05 ms
- API latency p95: 5.50 ms
- API latency max: 5.51 ms
- Average stage timings:
- `compute_features`: 0.83 ms
- `compute_shap_values`: 0.41 ms
- `get_baseline_data`: 0.00 ms
- `get_pump_data`: 0.00 ms
- `model_predict`: 0.69 ms
- `resolve_symbol`: 0.04 ms
- `total`: 2.01 ms

### warm

- Round-trip mean: 2.02 ms
- Round-trip p50: 1.72 ms
- Round-trip p95: 3.07 ms
- Round-trip max: 6.69 ms
- API latency mean: 1.24 ms
- API latency p50: 1.01 ms
- API latency p95: 1.87 ms
- API latency max: 4.51 ms
- Average stage timings:
- `compute_features`: 0.00 ms
- `compute_shap_values`: 0.42 ms
- `get_baseline_data`: 0.00 ms
- `get_pump_data`: 0.00 ms
- `model_predict`: 0.74 ms
- `resolve_symbol`: 0.05 ms
- `total`: 1.24 ms

### cold

- Round-trip mean: 5.78 ms
- Round-trip p50: 5.59 ms
- Round-trip p95: 6.24 ms
- Round-trip max: 6.24 ms
- API latency mean: 5.07 ms
- API latency p50: 4.78 ms
- API latency p95: 5.51 ms
- API latency max: 5.51 ms
- Average stage timings:
- `compute_features`: 4.16 ms
- `compute_shap_values`: 0.39 ms
- `get_baseline_data`: 0.01 ms
- `get_pump_data`: 0.01 ms
- `model_predict`: 0.47 ms
- `resolve_symbol`: 0.02 ms
- `total`: 5.07 ms

### Notes

- This is the cleaner architecture comparison because it removes live HTTP overhead and focuses on warm versus cold application cost.
- Cold requests stayed roughly 4x slower than warm requests, and feature computation remained the dominant cost center.

## Streaming Throughput

- Date: `2026-04-02`
- Commit: `763ef85`
- Environment: `synthetic watchlists using fake producer messages and patched consumer cache`
- Command: `uv run python -m scripts.benchmark_streaming --symbol-counts 10 50 100 250 500`

### 10 symbols

- Baseline publish: 0.08 ms
- Pump publish: 0.06 ms
- Consumer process: 0.69 ms
- End to end: 1.16 ms
- Throughput: 8631.55 symbols/sec

### 50 symbols

- Baseline publish: 0.29 ms
- Pump publish: 0.27 ms
- Consumer process: 1.96 ms
- End to end: 2.63 ms
- Throughput: 18977.44 symbols/sec

### 100 symbols

- Baseline publish: 0.52 ms
- Pump publish: 0.56 ms
- Consumer process: 3.85 ms
- End to end: 5.06 ms
- Throughput: 19781.09 symbols/sec

### 250 symbols

- Baseline publish: 1.19 ms
- Pump publish: 1.21 ms
- Consumer process: 8.47 ms
- End to end: 11.02 ms
- Throughput: 22690.92 symbols/sec

### 500 symbols

- Baseline publish: 2.71 ms
- Pump publish: 2.67 ms
- Consumer process: 33.82 ms
- End to end: 39.34 ms
- Throughput: 12709.90 symbols/sec

### Notes

- This benchmark measures application pipeline cost only; it does not include a real Kafka broker or Redis server.
- Throughput scales well through 250 symbols, then drops at 500 symbols where consumer-side processing becomes noticeably steeper.

## Degraded Dependency

- Date: `2026-04-02`
- Commit: `763ef85`
- Environment: `FastAPI TestClient with injected Binance delay and failure`
- Command: `uv run python -m scripts.benchmark_degraded --iterations 10 --delay-ms 200 --fail`

### failure_path

- Request count: 10
- Error rate: 100.00%
- Status counts: `503=10`
- Mean latency: 407.61 ms
- Max latency: 411.10 ms

### Notes

- Each failed request included two injected 200 ms waits: one during symbol resolution and one during pump-data retrieval before the service returned `503`.
- This gives a baseline for how expensive dependency retries or slow upstreams will feel even when the application fails fast at the endpoint boundary.
