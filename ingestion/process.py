import pandas as pd
df = pd.read_csv("data/raw/list_pd_events.csv")

# print(df["Exchange"])
df = df.drop(columns=["Channel"])
# print(df.head(5))

print(df["success"].value_counts())
print(df['Currency'].value_counts().head(20))
