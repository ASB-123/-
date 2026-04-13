import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#data = yf.download("BTC-USD",interval="15min", period="60d")
data = yf.download("BTC-USD", start='2024-01-01', end='2026-01-01')

data['ma7'] = data["Close"].rolling(7).mean()
data['ma21'] = data["Close"].rolling(21).mean()
data['ma50'] = data["Close"].rolling(50).mean()

data = data.dropna()

plt.figure(figsize=(12,6))
#label給名字
plt.plot(data['Close'], label='BTC Price', color='gray')
plt.plot(data['ma7'], label='ma7', color='blue')
plt.plot(data['ma21'], label='ma21', color='red')
plt.plot(data['ma50'], label='ma50',color='green')

#legend呼叫出來, grid畫背景網格
plt.legend()
plt.grid(alpha= 0.4)
plt.title("BTC Moving Averages")
plt.show()
