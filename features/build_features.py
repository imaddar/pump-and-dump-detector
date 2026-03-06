import argparse
import json
from pathlib import Path

import pandas as pd


RAW_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "num_trades",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]

NUMERIC_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "num_trades",
    "taker_buy_base_volume",
]

DEFAULT_INPUT_DIR = Path("data/raw/binance")
DEFAULT_OUTPUT_PATH = Path("data/processed/features/features.parquet")
EPSILON = 1e-8


def parse_klines(klines: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(klines, columns=RAW_COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for column in NUMERIC_COLUMNS:
        df[column] = df[column].astype(float)

    df["candle_range"] = df["high"] - df["low"]
    safe_volume = df["volume"].where(df["volume"] != 0)
    df["taker_buy_ratio"] = df["taker_buy_base_volume"].div(safe_volume)
    df["taker_buy_ratio"] = df["taker_buy_ratio"].fillna(0.0)
    return df


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / (denominator + EPSILON))


def safe_zscore(value: float, mean: float, std: float) -> float:
    return float((value - mean) / (std + EPSILON))


def price_acceleration(close_prices: pd.Series) -> float:
    returns = close_prices.pct_change()
    acceleration = returns.diff().abs().fillna(0.0)
    return float(acceleration.max())


def build_feature_row(raw_path: Path) -> dict:
    with raw_path.open() as file:
        payload = json.load(file)

    metadata = payload["metadata"]
    candles = parse_klines(payload["candles"])
    baseline = parse_klines(payload["baseline"])

    baseline_volume_mean = float(baseline["volume"].mean())
    baseline_volume_std = float(baseline["volume"].std())
    baseline_trade_count_mean = float(baseline["num_trades"].mean())
    baseline_trade_count_std = float(baseline["num_trades"].std())
    baseline_candle_range_mean = float(baseline["candle_range"].mean())
    baseline_candle_range_std = float(baseline["candle_range"].std())

    pump_peak_volume = float(candles["volume"].max())
    pump_peak_trades = float(candles["num_trades"].max())
    pump_peak_range = float(candles["candle_range"].max())

    return {
        "file": raw_path.name,
        "currency": metadata["currency"],
        "symbol": metadata.get("symbol"),
        "pump_date": pd.to_datetime(metadata["pump_date"], utc=True),
        "success": int(metadata["success"]),
        "data_source": metadata.get("data_source"),
        "price_change_max": safe_ratio(
            float(candles["close"].max()) - float(candles["close"].iloc[0]),
            float(candles["close"].iloc[0]),
        ),
        "taker_buy_ratio_peak": float(candles["taker_buy_ratio"].max()),
        "vol_burst_max": pump_peak_volume,
        "trade_count_max": pump_peak_trades,
        "price_acceleration": price_acceleration(candles["close"]),
        "baseline_volume_mean": baseline_volume_mean,
        "baseline_volume_std": baseline_volume_std,
        "baseline_trade_count_mean": baseline_trade_count_mean,
        "baseline_trade_count_std": baseline_trade_count_std,
        "baseline_candle_range_mean": baseline_candle_range_mean,
        "baseline_candle_range_std": baseline_candle_range_std,
        "vol_zscore_peak": safe_zscore(
            pump_peak_volume,
            baseline_volume_mean,
            baseline_volume_std,
        ),
        "vol_ratio_vs_7d": safe_ratio(pump_peak_volume, baseline_volume_mean),
        "trade_count_zscore": safe_zscore(
            pump_peak_trades,
            baseline_trade_count_mean,
            baseline_trade_count_std,
        ),
        "range_expansion_ratio": safe_ratio(
            pump_peak_range,
            baseline_candle_range_mean,
        ),
    }


def build_features_frame(input_dir: Path) -> pd.DataFrame:
    rows = [build_feature_row(path) for path in sorted(input_dir.glob("*.json"))]
    return pd.DataFrame(rows)


def write_features(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(output_path, index=False)
    except ImportError as exc:
        raise RuntimeError(
            "Writing parquet requires an optional parquet engine such as pyarrow."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-event pump features.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing raw Binance JSON files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Parquet output path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = build_features_frame(args.input_dir)
    write_features(df, args.output_path)
    print(f"Wrote {len(df)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
