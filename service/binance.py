from datetime import datetime, timedelta
import requests

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


def get_pump_data(symbol:str, pump_time:datetime) -> list[list]:

    start_ms = int((pump_time - timedelta(minutes=30)).timestamp() * 1000)
    end_ms   = int((pump_time + timedelta(minutes=30)).timestamp() * 1000)
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
    except requests.exceptions.ConnectionError as e:
        raise BinanceConnectionError(f"Could not connect to Binance API when trying to fetch pump data for symbol {symbol} at time {pump_time}")
    
    if response.status_code != 200:
        raise BinanceConnectionError(f"Received status code {response.status_code} from Binance API when trying to fetch pump data for symbol {symbol} at time {pump_time}")
    if not data:
        raise BinanceNoDataError(f"No data returned from Binance API when trying to fetch pump data for symbol {symbol} at time {pump_time}")
    return data


def get_baseline_data(symbol: str, pump_time:datetime) -> list[list]:

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
    except requests.exceptions.ConnectionError as e:
        raise BinanceConnectionError(f"Could not connect to Binance API when trying to fetch pump data for symbol {symbol} at time {pump_time}")
    
    if response.status_code != 200:
        raise BinanceConnectionError(f"Received status code {response.status_code} from Binance API when trying to fetch pump data for symbol {symbol} at time {pump_time}")
    if not data:
        raise BinanceNoDataError(f"No data returned from Binance API when trying to fetch pump data for symbol {symbol} at time {pump_time}")
    
    return data



def resolve_symbol(symbol:str):
    suffixes = ["", "USDT", "BTC", "ETH"]
    for suffix in suffixes:
        try:
            response = requests.get(f"https://api.binance.com/api/v3/exchangeInfo?symbol={symbol + suffix}")
            if response.status_code == 200:
                return symbol + suffix
        except requests.exceptions.ConnectionError as e:
            raise BinanceConnectionError(f"Could not connect to Binance API when trying to resolve symbol {symbol + suffix}")
        
    raise BinanceNoDataError(f"Could not resolve symbol {symbol} with any suffixes {suffixes}")
    