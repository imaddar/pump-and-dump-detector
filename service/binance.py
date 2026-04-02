from datetime import datetime, timedelta
import logging
import time
import requests

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = "https://api.binance.com"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 0.5


class BinanceConnectionError(ConnectionError):
    # if we cannot connect to binance (based on status code from API), we return this error
    def __init__(self, message="Failed to connect to Binance API"):
        self.message = message
        super().__init__(message)


class BinanceNoDataError(ValueError):
    # if we can connect but we get back empty information, we return this error
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def get_pump_data(symbol: str, pump_time: datetime):
    start_time = pump_time - timedelta(minutes=30)
    end_time   = pump_time + timedelta(minutes=30)
    start_ms   = int(start_time.timestamp() * 1000)
    end_ms     = int(end_time.timestamp() * 1000)

    response = binance_get(
        "/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": "1m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        },
        error_context=f"fetching pump data for {symbol} at {pump_time}",
    )
    data = response.json()

    if response.status_code != 200:
        msg = f"Binance returned status {response.status_code} for pump data request — {symbol} at {pump_time}"
        logger.error(msg)
        raise BinanceConnectionError(msg)

    if not data:
        msg = f"No pump data returned from Binance for {symbol} at {pump_time}"
        logger.warning(msg)
        raise BinanceNoDataError(msg)

    logger.info(f"Fetched {len(data)} pump candles for {symbol}")
    return data, start_time, end_time


def get_baseline_data(symbol: str, pump_time: datetime) -> list[list]:
    baseline_start_ms = int((pump_time - timedelta(days=7)).timestamp() * 1000)
    baseline_end_ms   = int((pump_time - timedelta(minutes=30)).timestamp() * 1000)

    response = binance_get(
        "/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": "1h",
            "startTime": baseline_start_ms,
            "endTime": baseline_end_ms,
            "limit": 1000,
        },
        error_context=f"fetching baseline data for {symbol} at {pump_time}",
    )
    data = response.json()

    if response.status_code != 200:
        msg = f"Binance returned status {response.status_code} for baseline data request — {symbol} at {pump_time}"
        logger.error(msg)
        raise BinanceConnectionError(msg)

    if not data:
        msg = f"No baseline data returned from Binance for {symbol} at {pump_time}"
        logger.warning(msg)
        raise BinanceNoDataError(msg)

    logger.info(f"Fetched {len(data)} baseline candles for {symbol}")
    return data


def resolve_symbol(symbol: str) -> str:
    suffixes = ["", "USDT", "BTC", "ETH"]

    for suffix in suffixes:
        candidate = symbol + suffix
        response = binance_get(
            "/api/v3/exchangeInfo",
            params={"symbol": candidate},
            error_context=f"resolving symbol {candidate}",
        )
        if response.status_code == 200:
            resolved = candidate
            logger.info(f"Resolved symbol {symbol!r} → {resolved!r}")
            return resolved

    msg = f"Could not resolve {symbol!r} with any suffixes {suffixes}"
    logger.warning(msg)
    raise BinanceNoDataError(msg)


def binance_get(path: str, params: dict, error_context: str) -> requests.Response:
    last_exception: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                f"{BINANCE_BASE_URL}{path}",
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_exception = exc
            if attempt == MAX_RETRIES:
                break
            logger.warning(
                "Binance request failed on attempt %s/%s while %s: %s",
                attempt,
                MAX_RETRIES,
                error_context,
                exc,
            )
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            continue

        return response

    msg = f"Could not connect to Binance API while {error_context}"
    logger.error(msg)
    raise BinanceConnectionError(msg) from last_exception
