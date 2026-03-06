import json
import pandas as pd
from pathlib import Path

files = list(Path("data/raw/binance").glob("*.json"))

rows = []
for f in files:
    with open(f) as file:
        data = json.load(file)
    rows.append({
        "file":         f.name,
        "currency":     data["metadata"]["currency"],
        "pump_date":    data["metadata"]["pump_date"],
        "success":      data["metadata"]["success"],
        "data_source":  data["metadata"]["data_source"],
        "n_candles":    len(data["candles"]),
        "n_baseline":   len(data["baseline"]),
    })

df = pd.DataFrame(rows)

print(f"Total files:        {len(df)}")
print(f"Successful pumps:   {df['success'].sum()}")
print(f"Failed pumps:       {(df['success'] == 0).sum()}")
print(f"Avg candles:        {df['n_candles'].mean():.1f}")
print(f"Missing baseline:   {(df['n_baseline'] == 0).sum()}")
print(f"Avg baseline candles: {df['n_baseline'].mean():.1f}")
print(f"Min baseline candles: {df['n_baseline'].min()}")