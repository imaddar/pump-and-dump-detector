import pandas as pd

EPSILON = 1e-8

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

# feature names the model was trained on — order matters at inference time
FEATURE_COLUMNS = [
    "price_change_max",
    "taker_buy_ratio_peak",
    "vol_burst_max",
    "trade_count_max",
    "price_acceleration",
    "baseline_volume_mean",
    "baseline_volume_std",
    "baseline_trade_count_mean",
    "baseline_trade_count_std",
    "baseline_candle_range_mean",
    "baseline_candle_range_std",
    "vol_zscore_peak",
    "vol_ratio_vs_7d",
    "trade_count_zscore",
    "range_expansion_ratio",
]


def parse_klines(klines: list[list]) -> pd.DataFrame:
    """Convert raw Binance kline list into a typed DataFrame."""
    df = pd.DataFrame(klines, columns=RAW_COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for column in NUMERIC_COLUMNS:
        df[column] = df[column].astype(float)

    df["candle_range"] = df["high"] - df["low"]
    safe_volume = df["volume"].where(df["volume"] != 0)
    df["taker_buy_ratio"] = df["taker_buy_base_volume"].div(safe_volume).fillna(0.0)
    return df


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / (denominator + EPSILON))


def safe_zscore(value: float, mean: float, std: float) -> float:
    return float((value - mean) / (std + EPSILON))


def price_acceleration(close_prices: pd.Series) -> float:
    returns = close_prices.pct_change()
    acceleration = returns.diff().abs().fillna(0.0)
    return float(acceleration.max())


def compute_features(pump_candles: list[list], baseline_candles: list[list]) -> dict:
    """
    Compute the full feature row from raw Binance kline lists.

    Parameters
    ----------
    pump_candles   : raw klines from the ±30min pump window (1m interval)
    baseline_candles : raw klines from the 7-day lookback (1h interval)

    Returns
    -------
    dict of feature_name -> float, keyed by FEATURE_COLUMNS
    """
    candles  = parse_klines(pump_candles)
    baseline = parse_klines(baseline_candles)

    baseline_volume_mean       = float(baseline["volume"].mean())
    baseline_volume_std        = float(baseline["volume"].std())
    baseline_trade_count_mean  = float(baseline["num_trades"].mean())
    baseline_trade_count_std   = float(baseline["num_trades"].std())
    baseline_candle_range_mean = float(baseline["candle_range"].mean())
    baseline_candle_range_std  = float(baseline["candle_range"].std())

    pump_peak_volume = float(candles["volume"].max())
    pump_peak_trades = float(candles["num_trades"].max())
    pump_peak_range  = float(candles["candle_range"].max())

    return {
        "price_change_max": safe_ratio(
            float(candles["close"].max()) - float(candles["close"].iloc[0]),
            float(candles["close"].iloc[0]),
        ),
        "taker_buy_ratio_peak":    float(candles["taker_buy_ratio"].max()),
        "vol_burst_max":           pump_peak_volume,
        "trade_count_max":         pump_peak_trades,
        "price_acceleration":      price_acceleration(candles["close"]),
        "baseline_volume_mean":    baseline_volume_mean,
        "baseline_volume_std":     baseline_volume_std,
        "baseline_trade_count_mean": baseline_trade_count_mean,
        "baseline_trade_count_std":  baseline_trade_count_std,
        "baseline_candle_range_mean": baseline_candle_range_mean,
        "baseline_candle_range_std":  baseline_candle_range_std,
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