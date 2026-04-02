import pandas as pd
from math import sqrt

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


def sample_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return float(sqrt(variance))


def compute_features_from_arrays(pump_candles: list[list], baseline_candles: list[list]) -> dict:
    pump_closes = [float(candle[4]) for candle in pump_candles]
    pump_volumes = [float(candle[5]) for candle in pump_candles]
    pump_trades = [float(candle[8]) for candle in pump_candles]
    pump_taker_buy = [float(candle[9]) for candle in pump_candles]
    pump_ranges = [float(candle[2]) - float(candle[3]) for candle in pump_candles]

    baseline_volumes = [float(candle[5]) for candle in baseline_candles]
    baseline_trades = [float(candle[8]) for candle in baseline_candles]
    baseline_ranges = [float(candle[2]) - float(candle[3]) for candle in baseline_candles]

    taker_buy_ratio_peak = max(
        safe_ratio(taker_buy, volume) if volume != 0 else 0.0
        for taker_buy, volume in zip(pump_taker_buy, pump_volumes, strict=False)
    )

    returns = [
        float((current - previous) / previous)
        for previous, current in zip(pump_closes, pump_closes[1:], strict=False)
    ]
    acceleration_values = [
        abs(current - previous)
        for previous, current in zip(returns, returns[1:], strict=False)
    ]

    baseline_volume_mean = float(sum(baseline_volumes) / len(baseline_volumes))
    baseline_trade_count_mean = float(sum(baseline_trades) / len(baseline_trades))
    baseline_candle_range_mean = float(sum(baseline_ranges) / len(baseline_ranges))
    baseline_volume_std = sample_std(baseline_volumes)
    baseline_trade_count_std = sample_std(baseline_trades)
    baseline_candle_range_std = sample_std(baseline_ranges)

    pump_peak_volume = max(pump_volumes)
    pump_peak_trades = max(pump_trades)
    pump_peak_range = max(pump_ranges)

    return {
        "price_change_max": safe_ratio(max(pump_closes) - pump_closes[0], pump_closes[0]),
        "taker_buy_ratio_peak": float(taker_buy_ratio_peak),
        "vol_burst_max": float(pump_peak_volume),
        "trade_count_max": float(pump_peak_trades),
        "price_acceleration": float(max(acceleration_values, default=0.0)),
        "baseline_volume_mean": baseline_volume_mean,
        "baseline_volume_std": baseline_volume_std,
        "baseline_trade_count_mean": baseline_trade_count_mean,
        "baseline_trade_count_std": baseline_trade_count_std,
        "baseline_candle_range_mean": baseline_candle_range_mean,
        "baseline_candle_range_std": baseline_candle_range_std,
        "vol_zscore_peak": safe_zscore(pump_peak_volume, baseline_volume_mean, baseline_volume_std),
        "vol_ratio_vs_7d": safe_ratio(pump_peak_volume, baseline_volume_mean),
        "trade_count_zscore": safe_zscore(pump_peak_trades, baseline_trade_count_mean, baseline_trade_count_std),
        "range_expansion_ratio": safe_ratio(pump_peak_range, baseline_candle_range_mean),
    }


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
    return compute_features_from_arrays(pump_candles, baseline_candles)
