import yfinance as yf
import pandas as pd

data = yf.download(["BTC-USD", "ETH-USD"], start="2023-01-01", end="2023-12-31")

close = data["Close"]

print(close.head())

print(close["BTC-USD"].head())

print(close["ETH-USD"].head())