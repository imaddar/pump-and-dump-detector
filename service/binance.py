from datetime import datetime, timedelta
import logging
import requests

logger = logging.getLogger(__name__)


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

    try:
        response = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol":    symbol,
                "interval":  "1m",
                "startTime": start_ms,
                "endTime":   end_ms,
                "limit":     1000
            }
        )
        data = response.json()
    except requests.exceptions.ConnectionError:
        msg = f"Could not connect to Binance API when fetching pump data for {symbol} at {pump_time}"
        logger.error(msg)
        raise BinanceConnectionError(msg)

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

    try:
        response = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol":    symbol,
                "interval":  "1h",
                "startTime": baseline_start_ms,
                "endTime":   baseline_end_ms,
                "limit":     1000
            }
        )
        data = response.json()
    except requests.exceptions.ConnectionError:
        msg = f"Could not connect to Binance API when fetching baseline data for {symbol} at {pump_time}"
        logger.error(msg)
        raise BinanceConnectionError(msg)

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
        try:
            response = requests.get(
                f"https://api.binance.com/api/v3/exchangeInfo?symbol={symbol + suffix}"
            )
            if response.status_code == 200:
                resolved = symbol + suffix
                logger.info(f"Resolved symbol {symbol!r} → {resolved!r}")
                return resolved
        except requests.exceptions.ConnectionError:
            msg = f"Could not connect to Binance API when resolving symbol {symbol + suffix}"
            logger.error(msg)
            raise BinanceConnectionError(msg)

    msg = f"Could not resolve {symbol!r} with any suffixes {suffixes}"
    logger.warning(msg)
    raise BinanceNoDataError(msg)