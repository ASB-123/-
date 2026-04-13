"""
    檢視BTC跟ETH的關聯性, 做一個小回測
"""
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

df = yf.download(["BTC-USD", "ETH-USD"], start='2023-01-01', end='2024-01-01')

btc = df['Close']['BTC-USD']

ema12 = btc.ewm(span=12, adjust=False).mean()
ema26 = btc.ewm(span=26, adjust=False).mean()

DIF = ema12 - ema26
DEA = DIF.ewm(span=9, adjust=False).mean()

signal = pd.Series(0, index=btc.index)

signal[DIF > DEA] = 1
signal[DIF < DEA] = -1

returns = btc.pct_change()

strategy_returns = signal.shift(1) * returns

cum_strategy = (1 + strategy_returns).cumprod()
cum_btc = (1 + returns).cumprod()

plt.figure(figsize=(12,6))

plt.plot(cum_strategy, label='Strategy')
#plt.plot(df['BTC-USD'], label= 'BTC')
plt.plot(cum_btc, label='Buy & Hold')
plt.legend()

plt.title("Strategy Vs Buy & Hold")
plt.grid(alpha= 0.3)

plt.show()