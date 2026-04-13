import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

data = yf.download("BTC-USD", interval= "15m", period= "60d")

df = data[["Close"]].rename(columns= {"Close":"price"})

df["return"] = df["price"].pct_change(fill_method=None)
df = df.dropna()

print(df)

plt.hist(df["return"].dropna(), bins=50)

plt.title("BTC Return Distribution")
plt.xlabel("Return")
plt.ylabel("Frequency")

plt.show()
