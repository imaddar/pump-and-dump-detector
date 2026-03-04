import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# Define time window
today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
yesterday = today - timedelta(days=1)

start_ms = int(yesterday.timestamp() * 1000)
end_ms   = int(today.timestamp() * 1000)

# Pull klines
response = requests.get(
    "https://api.binance.us/api/v3/klines",
    params={
        "symbol":    "BTCUSDT",
        "interval":  "1m",
        "startTime": start_ms,
        "endTime":   end_ms,
        "limit":     1000
    }
)

# Parse into DataFrame
df = pd.DataFrame(response.json(), columns=[
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "num_trades",
    "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
])

# Clean up
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
df = df.drop(columns=["ignore"])

for col in ["open", "high", "low", "close", "volume", 
            "quote_volume", "taker_buy_base_volume", 
            "taker_buy_quote_volume"]:
    df[col] = df[col].astype(float)

df["num_trades"] = df["num_trades"].astype(int)

print(df.head())
print(f"\nRows: {len(df)}")