# Pump-and-Dump Detector Architecture

## Purpose of This Document

This document is a detailed technical map of the repository as it exists today. It is meant to explain:

- how the codebase is partitioned
- how data moves through the system
- which files own which responsibilities
- why specific design decisions were made
- where the architecture is intentionally incomplete or still evolving

The project is organized around one core product idea:

1. collect historical market data around known pump events
2. transform raw exchange candles into a stable feature vector
3. train a binary classifier that predicts pump risk
4. serve that classifier behind an API that can score a symbol and explain the result

Everything in the repository either supports that pipeline directly or exists as scaffolding for future expansion.

## System Summary

At a high level, the repository implements an offline-to-online machine learning workflow:

- Offline ingestion scripts gather labeled market snapshots from Binance.
- Feature engineering code converts those raw windows into model-ready numeric features.
- Training scripts fit and tune a LightGBM binary classifier.
- Model metadata stores the model threshold, quality metrics, and exact feature order needed at inference time.
- A FastAPI service loads the trained model and metadata, fetches live Binance data on demand, computes the same features, and returns a risk score plus SHAP-based explanations.
- Tests guard the feature contract, API shape, and saved model quality.

This is a pragmatic architecture rather than a framework-heavy one. The code favors direct scripts and plain modules over formal pipelines, orchestration layers, or domain abstractions.

## Architectural Principles Visible in the Code

Several design choices repeat across the repository:

### 1. Feature parity between training and inference is treated as the central contract

The most important invariant in the system is that online inference must compute the exact same feature set used during model training.

That is why:

- [`features/feature_engineering.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/feature_engineering.py) owns a single shared `FEATURE_COLUMNS` list
- the training workflow writes `feature_columns` into [`modeling/models/lgbm_tuned.json`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/models/lgbm_tuned.json)
- the API reconstructs a one-row `DataFrame` using that stored ordering before calling `model.predict()`

This is a strong decision because tabular ML systems fail quietly when feature order drifts. The repository avoids that class of bug by making feature order explicit data, not an assumption.

### 2. Scripts are favored over orchestration frameworks

The ingestion, training, and SHAP reporting flows are mostly plain Python scripts. That keeps the system simple to run locally and easy to inspect. The tradeoff is that execution is less composable and less resumable than a formal workflow engine would provide.

### 3. The repository is split by lifecycle stage

Directories reflect pipeline stages more than technical layers:

- ingestion
- features
- modeling
- service
- streaming
- tests

This is a sensible choice for an ML project because developers usually reason in terms of dataset creation, feature creation, training, and serving rather than in terms of controllers/services/repositories.

### 4. The current implementation optimizes for clarity over abstraction depth

Most files are short and direct. The code does not introduce wrappers unless they solve a specific problem:

- `service/binance.py` wraps exchange access because API serving needs reusable error translation
- `modeling/shap_analysis.py` wraps SHAP utilities because both the report script and the API need the same explanation primitives

Elsewhere, the repository avoids indirection.

## Repository Layout

### Root-level files

- [`pyproject.toml`](/Users/imaddar/git-repos/pump-and-dump-detector/pyproject.toml): Python package metadata and dependencies.
- [`uv.lock`](/Users/imaddar/git-repos/pump-and-dump-detector/uv.lock): locked dependency graph for reproducible installs.
- [`Dockerfile`](/Users/imaddar/git-repos/pump-and-dump-detector/Dockerfile): container build for the API service.
- [`docker-compose.yml`](/Users/imaddar/git-repos/pump-and-dump-detector/docker-compose.yml): local multi-service environment for Redis, Kafka, Zookeeper, and the API.
- [`README.md`](/Users/imaddar/git-repos/pump-and-dump-detector/README.md): currently empty, which makes this architecture document especially useful as the current source of project narrative.
- [`architecture.md`](/Users/imaddar/git-repos/pump-and-dump-detector/architecture.md): this document.

### Data and experimentation directories

- [`data/`](/Users/imaddar/git-repos/pump-and-dump-detector/data): raw and processed datasets.
- [`notebooks/`](/Users/imaddar/git-repos/pump-and-dump-detector/notebooks): exploratory analysis notebook(s).
- [`logs/`](/Users/imaddar/git-repos/pump-and-dump-detector/logs): runtime logs written by scripts and reporting jobs.
- [`monitoring/`](/Users/imaddar/git-repos/pump-and-dump-detector/monitoring): reserved for future monitoring work, currently empty.

### Execution-stage directories

- [`ingestion/`](/Users/imaddar/git-repos/pump-and-dump-detector/ingestion): historical data collection scripts.
- [`features/`](/Users/imaddar/git-repos/pump-and-dump-detector/features): feature extraction and audit code.
- [`modeling/`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling): training, tuning, interpretation, and saved artifacts.
- [`service/`](/Users/imaddar/git-repos/pump-and-dump-detector/service): online inference API.
- [`streaming/`](/Users/imaddar/git-repos/pump-and-dump-detector/streaming): streaming-oriented cache and future event processing components.
- [`tests/`](/Users/imaddar/git-repos/pump-and-dump-detector/tests): automated tests.

### CI

- [`.github/workflows/ci.yml`](/Users/imaddar/git-repos/pump-and-dump-detector/.github/workflows/ci.yml): GitHub Actions workflow that installs dependencies and runs the test suite on pushes and pull requests targeting `main`.

## End-to-End Data Flow

The architecture is easiest to understand by following the data through the system.

### Phase 1: event labels and raw market collection

Historical pump events are represented in [`data/raw/list_pd_events.csv`](/Users/imaddar/git-repos/pump-and-dump-detector/data/raw/list_pd_events.csv). The ingestion script reads that CSV, filters it to Binance events, and uses those rows as the supervision source for data collection.

[`ingestion/binance_fetch.py`](/Users/imaddar/git-repos/pump-and-dump-detector/ingestion/binance_fetch.py) performs the following steps:

1. load the labeled pump-event CSV
2. keep only Binance rows
3. derive a target symbol by appending `BTC` to the event currency
4. fetch a ±30 minute 1-minute-candle window around the event
5. fetch a 7-day 1-hour baseline window leading up to the event
6. save both into one JSON payload under `data/raw/binance/`
7. encode the event label in metadata and filename
8. write a status CSV summarizing successes, failures, and empties

Each raw JSON file contains:

- `metadata`
- `candles`
- `baseline`

This is a useful design because a single event file is self-contained. Training does not need to rejoin labels from some separate table later.

### Phase 2: feature construction

The feature layer translates raw exchange payloads into a stable, numeric representation.

[`features/feature_engineering.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/feature_engineering.py) is the core of the architecture. It does three jobs:

- parse raw Binance kline arrays into typed `pandas` frames
- derive intermediate series like `candle_range` and `taker_buy_ratio`
- compute the final model feature dictionary

The code is intentionally built around exchange-native payloads rather than around ORM-like event objects. That keeps preprocessing close to the raw data and reduces translation layers.

The current feature set mixes two types of signals:

- pump-window intensity signals
- deviations from baseline behavior

Examples:

- `price_change_max`
- `vol_burst_max`
- `trade_count_max`
- `price_acceleration`
- `vol_zscore_peak`
- `range_expansion_ratio`

This is a strong modeling decision. Pump-and-dump behavior is not only about absolute volume or price movement; it is about abnormal movement relative to a token’s recent normal state. The baseline statistics encode that context.

### Phase 3: processed feature dataset

The processed dataset lives at [`data/processed/features/features.parquet`](/Users/imaddar/git-repos/pump-and-dump-detector/data/processed/features/features.parquet).

The intended role of [`features/build_features.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/build_features.py) is to transform raw JSON event files into that parquet dataset. Right now, that file is incomplete and contains only setup boilerplate. That tells us the processed parquet was likely created through an earlier version of the script or an external/manual workflow.

Architecturally, this means the repository has a clear conceptual pipeline but an incomplete reproducibility layer for rebuilding processed features from raw data using only committed code.

[`features/data_audit.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/data_audit.py) provides a lightweight integrity check over the raw event JSON files. It is not part of the production path; it exists to inspect data coverage and baseline completeness.

### Phase 4: model training and tuning

The model-training stage consumes the processed parquet dataset.

[`modeling/training_basic.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/training_basic.py) is the simplest training path:

- load numeric columns from parquet
- split train/validation with stratification
- train a binary LightGBM model
- save a basic model artifact
- print core classification metrics

This file is useful as a baseline or early experiment, not as the main production training path.

[`modeling/hyperparameter_tuning.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/hyperparameter_tuning.py) is the real training pipeline. It:

- loads the same parquet dataset
- preserves a deterministic train/validation split
- tunes LightGBM hyperparameters with Optuna
- evaluates models using average precision instead of ROC AUC
- finds a threshold that maximizes validation F1
- saves the tuned model to `modeling/models/lgbm_tuned.txt`
- saves serving metadata to `modeling/models/lgbm_tuned.json`

Two design choices matter here:

- Average precision is used as the optimization metric. That makes sense for imbalanced-event detection, where ranking positive cases well is more meaningful than generic ROC separation.
- Threshold selection is treated as a first-class artifact. Instead of hardcoding `0.5`, the code stores the best validation threshold in metadata and reuses it during inference.

This separation between probability estimation and classification threshold is a mature design choice. It acknowledges that a model’s operating point is part of the product behavior, not just a training detail.

### Phase 5: model interpretation

[`modeling/shap_analysis.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/shap_analysis.py) contains reusable SHAP helpers:

- model loading
- validation-data loading
- SHAP output normalization
- top-feature extraction
- plot saving

[`modeling/shap_report.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/shap_report.py) is a script wrapper around those helpers. It generates:

- summary plot
- bar-style feature importance plot
- waterfall plot for the highest predicted validation example

This is a good architectural split. The lower-level SHAP primitives are reusable by the API, while the report script is allowed to be procedural and output-oriented.

### Phase 6: online inference

[`service/app.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/app.py) serves the trained model using FastAPI.

The serving flow is:

1. at startup, load the LightGBM model, model metadata, and a SHAP explainer into `app.state`
2. accept a `POST /predict` request with a symbol and optional timestamp
3. resolve the symbol against Binance
4. fetch the pump window and baseline window from Binance in real time
5. compute the same features used during training
6. build a one-row feature frame ordered using saved `feature_columns`
7. run model inference
8. classify using the saved threshold
9. compute SHAP values for that single row
10. return a risk label, risk score, top signals, timestamps, latency, and model version

This is the serving heart of the project. It relies on the same feature module as training, which is the key architectural choice preserving parity.

## Detailed Module Breakdown

## `ingestion/`

### [`ingestion/binance_fetch.py`](/Users/imaddar/git-repos/pump-and-dump-detector/ingestion/binance_fetch.py)

Responsibility:

- historical offline collection of labeled Binance data for supervised training

Why it exists:

- the model needs known positive and negative historical examples
- raw exchange APIs are not suitable as a training dataset until they are frozen into local artifacts

Important design decisions:

- Data is stored as JSON, not CSV or parquet, at the raw layer.
  JSON preserves the nested exchange response shape and keeps metadata and arrays together.
- The pump window uses 1-minute candles while the baseline uses 1-hour candles.
  This captures short-term event dynamics while keeping baseline context compact.
- Labels are embedded directly in the raw file metadata.
  That simplifies downstream processing.

Tradeoffs:

- The script executes at import/runtime top level rather than exposing a `main()` function or reusable API.
  That makes it simple to run directly, but harder to test and compose.
- Requests are synchronous and sequential.
  That is easier to reason about but slower for large backfills.

### [`ingestion/ingestion.md`](/Users/imaddar/git-repos/pump-and-dump-detector/ingestion/ingestion.md)

This is a lightweight narrative note that confirms the intended architectural boundary: ingestion logic belongs here, and data storage belongs under `data/`.

## `features/`

### [`features/feature_engineering.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/feature_engineering.py)

Responsibility:

- canonical transformation from raw Binance candle arrays into model features

Why it is one of the most important files in the repository:

- it sits exactly on the boundary between raw market data and the ML model
- both training and serving depend on it
- any bug here affects the entire system

Key functions:

- `parse_klines()`: type coercion plus derivation of row-level helpers
- `safe_ratio()`: defensive division against zero or near-zero denominators
- `safe_zscore()`: defensive standardization
- `price_acceleration()`: captures abrupt changes in returns rather than only price direction
- `compute_features()`: single public feature contract

Important design decisions:

- raw Binance column names are centralized in `RAW_COLUMNS`
- numeric casting is explicit rather than inferred
- epsilon-protected math avoids runtime crashes and NaN-heavy outputs
- output is a plain dict keyed exactly by `FEATURE_COLUMNS`

This file is intentionally stateless. That is the right choice. Feature engineering code becomes much easier to test when it is pure and deterministic.

### [`features/build_features.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/build_features.py)

Intended responsibility:

- build the processed training dataset from raw event JSON files

Current state:

- incomplete
- contains logging and directory setup, but not the event-processing implementation

Architectural implication:

- the project’s conceptual pipeline is stronger than its current code-level automation for feature dataset reconstruction

This gap should be called out in any future walkthrough because it affects reproducibility.

### [`features/data_audit.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/data_audit.py)

Responsibility:

- inspect raw data coverage and basic collection quality

Why it matters:

- ML quality problems often start as data quality problems
- keeping audit logic separate from feature logic prevents the core feature module from accumulating ad hoc diagnostics

## `modeling/`

### [`modeling/training_basic.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/training_basic.py)

Responsibility:

- minimal baseline model training path

Why it likely exists:

- to prove the feature set can train a working binary classifier before introducing tuning complexity

Design notes:

- uses a stratified split, which is appropriate for imbalanced classification
- saves `X_train` as a LightGBM binary dataset, likely for faster reuse or experimentation

Limitations:

- saves to `lgbm_model.txt`, which differs from the tuned model naming used by the service
- does not persist serving metadata
- uses default thresholding behavior

### [`modeling/hyperparameter_tuning.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/hyperparameter_tuning.py)

Responsibility:

- production-oriented training and model artifact creation

Why it is the effective source of truth:

- the API loads the exact artifacts this script writes

Important design decisions:

- Optuna handles search instead of hand-edited parameter sweeps
- validation metric is `average_precision`
- early stopping is enabled
- threshold optimization is done after training rather than assumed
- model metadata includes `trained_at`, `threshold`, quality metrics, and `feature_columns`

That last point is especially important. The metadata file is not just bookkeeping. It is part of the serving contract.

### [`modeling/shap_analysis.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/shap_analysis.py)

Responsibility:

- reusable model explainability utilities

Design decisions:

- path constants are defined relative to the project root, which makes the module more portable
- SHAP output normalization handles the binary-classification shape differences that can arise across SHAP versions and model interfaces
- explanation extraction is designed for both full reports and per-request API summaries

This module is a good example of separating reusable library logic from script entrypoints.

### [`modeling/shap_report.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/shap_report.py)

Responsibility:

- generate human-readable explainability artifacts from the tuned model

Why it matters architecturally:

- it gives the repository an interpretation layer, not just prediction
- it supports project storytelling and model validation by showing what the model is actually reacting to

### [`modeling/models/`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/models)

Contents:

- `lgbm_basic.txt`
- `lgbm_tuned.txt`
- `lgbm_tuned.json`
- SHAP image outputs

Design decision:

- model artifacts are committed into the repository

Benefits:

- easy local startup
- API can run without a separate model registry
- tests can validate the same model the service serves

Tradeoffs:

- larger repository size
- artifact updates require code commits
- no formal version registry beyond `trained_at`

## `service/`

### [`service/schemas.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/schemas.py)

Responsibility:

- request and response validation for the API surface

Design decisions:

- `time` defaults to current UTC time, allowing “score now” requests
- `risk_score` is constrained to `[0, 1]`, which makes the response contract stricter and self-validating

This file keeps schema concerns separate from API logic, which is the correct boundary.

### [`service/binance.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/binance.py)

Responsibility:

- all Binance access used by the API

Key capabilities:

- resolve a symbol by trying common quote-asset suffixes
- fetch pump-window candles
- fetch baseline-window candles
- translate network/data problems into domain-specific exceptions

Why this abstraction exists:

- the API layer should not contain raw HTTP request logic
- external dependency failures need consistent exception handling

Important design decisions:

- explicit custom exceptions separate “could not connect” from “connected but got no usable data”
- symbol resolution is dynamic rather than assuming one quote asset

Tradeoffs:

- the resolver treats any HTTP 200 from `/exchangeInfo` as success; it does not inspect payload semantics in detail
- requests are still synchronous inside an async API handler, so concurrency is simpler but not fully non-blocking

### [`service/app.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/app.py)

Responsibility:

- FastAPI application assembly and inference endpoint implementation

Endpoints:

- `POST /predict`
- `GET /health`
- `GET /model/metrics`

Important design decisions:

- model loading happens once in lifespan startup, not per request
- metadata is loaded alongside the model
- SHAP explainer is also initialized once, which reduces repeated setup cost
- the API returns explanation data, not just a score

This last point is important for product design. A pump-risk score without supporting signals is difficult to trust. Returning `top_signals` makes the service easier to debug and easier to present to users.

Potential constraints:

- the endpoint depends on live Binance availability for every prediction
- there is no caching in the active request path yet
- synchronous I/O inside async handlers can limit throughput under load

## `streaming/`

### [`streaming/redis_client.py`](/Users/imaddar/git-repos/pump-and-dump-detector/streaming/redis_client.py)

Responsibility:

- simple Redis-backed cache primitives keyed by symbol and data type

What it suggests about the future architecture:

- the project intends to support a lower-latency or event-driven scoring path
- pump windows and baseline-derived values may eventually be cached instead of recomputed from Binance on every request

Design decisions:

- cache TTL differs by key type, implying pump data is expected to expire faster than baseline data
- the API is intentionally tiny: check, get, set

### [`streaming/producer.py`](/Users/imaddar/git-repos/pump-and-dump-detector/streaming/producer.py)

Current state:

- empty placeholder

Likely intended role:

- publish streaming market events into Kafka

### [`streaming/consumer.py`](/Users/imaddar/git-repos/pump-and-dump-detector/streaming/consumer.py)

Current state:

- empty placeholder

Likely intended role:

- consume streamed market events, compute or cache derived values, and possibly trigger alerting/scoring

Architecturally, `streaming/` is not part of the current working product path. It is a future-facing extension area.

## `tests/`

The tests reveal the intended invariants of the system more clearly than comments do.

### [`tests/test_feature_engineering.py`](/Users/imaddar/git-repos/pump-and-dump-detector/tests/test_feature_engineering.py)

This file protects the most important ML contract:

- parsed candle types are correct
- derived columns are correct
- feature output order matches `FEATURE_COLUMNS`
- computed values match known mock expectations
- feature ranges satisfy basic sanity constraints

This is exactly where strong tests belong in a tabular ML repository. Feature bugs are often more damaging than model bugs.

### [`tests/test_model_quality.py`](/Users/imaddar/git-repos/pump-and-dump-detector/tests/test_model_quality.py)

This test compares the committed tuned model’s current validation quality against the committed metadata quality.

Why this is useful:

- it catches accidental model artifact drift
- it ensures the shipped model still performs at or near its recorded benchmark

Why this is slightly unusual:

- it tests a persisted artifact, not just source code
- it assumes access to the processed parquet dataset during test execution

This is still a reasonable choice for a small ML project because model artifacts are part of the deliverable.

### [`tests/test_api.py`](/Users/imaddar/git-repos/pump-and-dump-detector/tests/test_api.py)

This file validates:

- health endpoint shape
- metrics endpoint shape
- predict endpoint shape
- request validation failures

The prediction test mocks Binance access functions so the test remains deterministic. That is an important design decision because the API should be tested as application logic, not as a live exchange integration test.

### [`tests/conftest.py`](/Users/imaddar/git-repos/pump-and-dump-detector/tests/conftest.py)

Provides a shared FastAPI `TestClient` fixture.

### [`tests/mock_feature_engineering_data.py`](/Users/imaddar/git-repos/pump-and-dump-detector/tests/mock_feature_engineering_data.py)

Defines reusable kline payloads that mirror the raw JSON structure written by ingestion.

That is a good testing design choice because the mocks reflect the real data shape rather than some simplified synthetic abstraction.

## Data Model and Contracts

There are several important contracts in the repository.

### Raw event contract

Each raw event JSON file contains:

- `metadata.currency`
- `metadata.symbol`
- `metadata.pump_date`
- `metadata.success`
- `metadata.data_source`
- `candles`
- `baseline`

This is the boundary between ingestion and feature engineering.

### Feature contract

The feature vector is defined by `FEATURE_COLUMNS` in [`features/feature_engineering.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/feature_engineering.py) and duplicated as saved metadata in [`modeling/models/lgbm_tuned.json`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/models/lgbm_tuned.json).

Current feature list:

- `price_change_max`
- `taker_buy_ratio_peak`
- `vol_burst_max`
- `trade_count_max`
- `price_acceleration`
- `baseline_volume_mean`
- `baseline_volume_std`
- `baseline_trade_count_mean`
- `baseline_trade_count_std`
- `baseline_candle_range_mean`
- `baseline_candle_range_std`
- `vol_zscore_peak`
- `vol_ratio_vs_7d`
- `trade_count_zscore`
- `range_expansion_ratio`

This is the boundary between feature engineering and the model.

### Model metadata contract

[`modeling/models/lgbm_tuned.json`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/models/lgbm_tuned.json) currently stores:

- `threshold`
- `pr_auc`
- `f1`
- `trained_at`
- `feature_columns`

This is the boundary between training and serving.

### API contract

The `POST /predict` request body is defined by [`service/schemas.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/schemas.py):

- `symbol: str`
- `time: datetime` with a UTC default

The response includes:

- `risk_label`
- `risk_score`
- `top_signals`
- `computed_at`
- `window_start`
- `window_end`
- `latency_ms`
- `model_version`

This is the boundary between the backend and any future UI or alerting client.

## Runtime Topology

### Local Python execution

Most of the repository runs as plain local Python scripts with `uv` managing environments and dependencies.

### API container

The [`Dockerfile`](/Users/imaddar/git-repos/pump-and-dump-detector/Dockerfile) packages the API service.

Important design decisions in the container build:

- uses `python:3.12-slim` for a smaller base image
- installs `uv` inside the container
- installs `libgomp1`, which LightGBM needs on slim images
- copies only serving-relevant files, not the entire repository

That final choice is especially good. It reduces image size and narrows the runtime surface area.

One subtle point: the Dockerfile copies `features/feature_engineering.py` into `features/`, but does not copy an `__init__.py`. Python 3 namespace package behavior makes this workable, but it is slightly implicit.

### Compose environment

[`docker-compose.yml`](/Users/imaddar/git-repos/pump-and-dump-detector/docker-compose.yml) provisions:

- Redis
- Zookeeper
- Kafka
- API

What this tells us:

- the current working API only strictly needs the API container
- Redis and Kafka are present because the architecture is expected to grow into caching and streaming use cases

This file is therefore partly “current infrastructure” and partly “planned infrastructure.”

## Design Decisions and Their Rationale

## Why LightGBM?

The repository uses LightGBM for the classifier. That is a sensible choice for this problem because:

- the feature space is tabular and numeric
- nonlinear interactions likely matter
- training speed is good
- model inference is lightweight
- SHAP explanations work well with tree models

This is a strong fit compared with deep learning, which would be heavier and harder to justify at the current feature scale.

## Why baseline-relative features?

Pump detection depends on anomaly detection within a token’s own trading context. Raw volume alone is not enough because one token’s normal volume may be another token’s extreme event. Baseline means, standard deviations, and ratios solve that problem.

## Why save threshold in metadata?

Model scores are probabilities or ranking signals. The threshold determines product behavior. Storing threshold in metadata keeps the API behavior aligned with the training decision rather than silently defaulting to `0.5`.

## Why compute explanations in the API?

Returning explanations directly from the prediction path makes the service much more useful operationally:

- users can inspect why a symbol was flagged
- developers can debug suspicious scores
- future frontends can display interpretable evidence without running a separate explanation pipeline

The tradeoff is extra inference latency.

## Why direct Binance fetches at request time?

The current architecture optimizes for simplicity and correctness:

- no separate market-data service
- no cache invalidation complexity
- no synchronization problem between live data and model scoring

The tradeoff is dependency on external latency and uptime.

## Why commit model artifacts?

For a small project, committed artifacts make development and demos dramatically simpler. There is no separate model registry, object store, or promotion system to maintain yet. The cost is that artifact lifecycle management is still repository-based.

## Current Gaps, Incomplete Areas, and Architectural Risks

This section is important because it explains where the codebase is still in transition.

### 1. `features/build_features.py` is incomplete

This is the biggest reproducibility gap in the repository. The processed parquet exists, but the code that should rebuild it is not fully present.

### 2. `streaming/producer.py` and `streaming/consumer.py` are placeholders

Kafka and Redis appear in infrastructure, but the streaming pipeline is not implemented yet.

### 3. `scripts/collect_all.sh` references a missing `ingestion/etherscan_fetch.py`

This means the script currently describes a broader ingestion vision than the committed code supports.

### 4. Serving uses synchronous HTTP inside async routes

FastAPI supports async handlers, but `requests` is blocking. Under higher concurrency, this can limit throughput. For the current project stage, this is acceptable, but it is an obvious future optimization point.

### 5. The model depends on external live data at prediction time

If Binance is unavailable or slow, prediction is unavailable or slow. The architecture already hints at caching through Redis, but that cache is not wired into the active request path yet.

### 6. Some repository directories are scaffolding rather than active architecture

Examples:

- `monitoring/` is empty
- `streaming/` is mostly unimplemented
- `README.md` is empty

That is not a problem, but it should be narrated honestly in any walkthrough.

## What Is Actually “Production-Critical” Today

If you strip the project down to the minimum set of files needed for the current working product, the critical path is:

- [`features/feature_engineering.py`](/Users/imaddar/git-repos/pump-and-dump-detector/features/feature_engineering.py)
- [`modeling/models/lgbm_tuned.txt`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/models/lgbm_tuned.txt)
- [`modeling/models/lgbm_tuned.json`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/models/lgbm_tuned.json)
- [`modeling/shap_analysis.py`](/Users/imaddar/git-repos/pump-and-dump-detector/modeling/shap_analysis.py)
- [`service/binance.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/binance.py)
- [`service/schemas.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/schemas.py)
- [`service/app.py`](/Users/imaddar/git-repos/pump-and-dump-detector/service/app.py)

Everything else either supports training, validation, infrastructure, exploration, or planned future functionality.

## Suggested Narrative for a Future README Walkthrough

When you later polish this into a project walkthrough, the cleanest narrative arc will probably be:

1. start with the product problem: detect likely pump-and-dump setups from market microstructure
2. explain the raw event dataset and how historical labels are collected
3. describe feature engineering as the center of the architecture
4. show why LightGBM plus baseline-relative features is the modeling choice
5. explain how the API recomputes those same features on live Binance data
6. end with explainability, testing, and future streaming/caching plans

That matches the actual shape of the codebase.

## Final Architectural Assessment

This repository is best described as a practical ML application with a clean core and unfinished outer layers.

The clean core is:

- raw event ingestion
- deterministic feature engineering
- LightGBM training/tuning
- model metadata
- FastAPI serving with SHAP explanations

The unfinished outer layers are:

- feature-dataset rebuild automation
- streaming ingestion/processing
- caching integration
- richer monitoring and documentation

That is a healthy state for a project at this stage. The important thing is that the central model contract is already explicit and shared across training and inference. That is the architectural decision that makes the rest of the system coherent.
