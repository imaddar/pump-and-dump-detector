import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

df = pd.read_csv("data/raw/list_pd_events.csv")
df = df[df["Exchange"] == "Binance"]
df = df.drop(columns=["Channel", "Exchange"])

df_mini = df

for coin in df_mini.itertuples():
    _, date, currency, success, pump_date = coin
    if pd.isna(pump_date):
        pump_date = date
    # define time window of pump
    pump_date = datetime.fromisoformat(pump_date)
    start_ms = int((pump_date - timedelta(minutes=30)).timestamp() * 1000)
    end_ms = int((pump_date + timedelta(minutes=30)).timestamp() * 1000)
    
    # fetch data from binance
    response = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={
            "symbol":    currency + "BTC",
            "interval":  "1m",
            "startTime": start_ms,
            "endTime":   end_ms,
            "limit":     1000
        }
    )
    print(currency + "BTC", response.json())
    break
    
    pumps_df = pd.DataFrame(response.json(), columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "num_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
    ])
    
    baseline_df = pd.DataFrame

