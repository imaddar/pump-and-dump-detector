import requests
import pandas as pd
import json
import os
import time
import logging
from datetime import datetime, timedelta

# ── logging setup ────────────────────────────────────────────────────────────
os.makedirs("logs/collection", exist_ok=True)
os.makedirs("data/raw/binance", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler("logs/collection/binance_collection.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── status tracking ───────────────────────────────────────────────────────────
status_rows = []

# ── load and filter data ──────────────────────────────────────────────────────
df = pd.read_csv("data/raw/list_pd_events.csv")
df = df[df["Exchange"] == "Binance"]
df = df.drop(columns=["Channel", "Exchange"])

logger.info(f"Starting collection for {len(df)} events")

# ── collection loop ───────────────────────────────────────────────────────────
for coin in df.itertuples():
    _, date, currency, success, pump_date = coin

    if pd.isna(pump_date):
        pump_date = date

    pump_date_dt = datetime.fromisoformat(pump_date.replace("Z", ""))
    timestamp_str = pump_date_dt.strftime("%Y%m%dT%H%M")
    symbol = currency + "BTC"

    start_ms = int((pump_date_dt - timedelta(minutes=30)).timestamp() * 1000)
    end_ms   = int((pump_date_dt + timedelta(minutes=30)).timestamp() * 1000)

    # ── fetch pump window ─────────────────────────────────────────────────────
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

    # ── error handling ────────────────────────────────────────────────────────
    if response.status_code != 200 or isinstance(data, dict):
        msg = data.get("msg", "unknown error") if isinstance(data, dict) else "bad status"
        logger.warning(f"FAILED  {symbol} — {msg}")
        status_rows.append({
            "currency": currency, "timestamp": timestamp_str,
            "symbol": symbol, "status": "failed", "reason": msg
        })
        # time.sleep(0.3)
        continue

    if len(data) == 0:
        logger.warning(f"EMPTY   {symbol} — no trades in window")
        status_rows.append({
            "currency": currency, "timestamp": timestamp_str,
            "symbol": symbol, "status": "empty", "reason": "no trades in window"
        })
        # time.sleep(0.3)
        continue

    # ── fetch baseline window ─────────────────────────────────────────────────
    baseline_start_ms = int((pump_date_dt - timedelta(days=7)).timestamp() * 1000)
    baseline_end_ms   = int((pump_date_dt - timedelta(minutes=30)).timestamp() * 1000)

    baseline_response = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={
            "symbol":    symbol,
            "interval":  "1h",
            "startTime": baseline_start_ms,
            "endTime":   baseline_end_ms,
            "limit":     1000
        }
    )

    baseline_data = baseline_response.json()

    if baseline_response.status_code != 200 or isinstance(baseline_data, dict):
        logger.warning(f"BASELINE FAILED  {symbol}")
        baseline_data = []

    # ── save raw json ─────────────────────────────────────────────────────────
    filename = f"data/raw/binance/{currency}_{timestamp_str}_{int(success)}.json"

    with open(filename, "w") as f:
        json.dump({
            "metadata": {
                "currency":   currency,
                "symbol":     symbol,
                "pump_date":  pump_date_dt.isoformat(),
                "success":    int(success),
                "data_source": "binance"
            },
            "candles":  data,
            "baseline": baseline_data
        }, f, indent=2)

    logger.info(f"SAVED   {filename}  ({len(data)} candles, {len(baseline_data)} baseline)")
    status_rows.append({
        "currency": currency, "timestamp": timestamp_str,
        "symbol": symbol, "status": "success", "reason": ""
    })

    # time.sleep(0.3)

# ── save status log ───────────────────────────────────────────────────────────
status_df = pd.DataFrame(status_rows)
status_df.to_csv("logs/collection/binance_status.csv", index=False)

# ── summary ───────────────────────────────────────────────────────────────────
total   = len(status_rows)
saved   = sum(1 for r in status_rows if r["status"] == "success")
failed  = sum(1 for r in status_rows if r["status"] == "failed")
empty   = sum(1 for r in status_rows if r["status"] == "empty")

logger.info(f"Collection complete — {saved} saved, {failed} failed, {empty} empty / {total} total")