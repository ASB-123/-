"""
    測試刪數據位置的影響
    失敗的測試，別管
"""
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
"""
df = yf.download('ETH-USD', start='2023-01-01', end='2026-01-01', auto_adjust=True)

# MACD
df['ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
df['ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
df['DIF'] = df['ema12'] - df['ema26']
df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()

# 太早清
df = df.dropna()

# 訊號
df['Signal'] = 0
df.loc[(df['DIF'] > df['DEA']) & (df['DIF'].shift(1) <= df['DEA'].shift(1)), 'Signal'] = 1
df.loc[(df['DIF'] < df['DEA']) & (df['DIF'].shift(1) >= df['DEA'].shift(1)), 'Signal'] = -1

# 持倉
df['Position'] = df['Signal'].replace(0, np.nan).ffill()
df['Position'] = df['Position'].clip(lower=0)
df['Position'] = df['Position'].shift(1)

# 報酬
df['returns'] = df['Close'].pct_change()
df['strategy'] = df['Position'] * df['returns']

# 資金曲線
df['equity_A'] = (1 + df['strategy']).cumprod()
"""
df = yf.download('ETH-USD', start='2023-01-01', end='2026-01-01', auto_adjust=True)

# MACD
df['ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
df['ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
df['DIF'] = df['ema12'] - df['ema26']
df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()

# 訊號
df['Signal'] = 0
df.loc[(df['DIF'] > df['DEA']) & (df['DIF'].shift(1) <= df['DEA'].shift(1)), 'Signal'] = 1
df.loc[(df['DIF'] < df['DEA']) & (df['DIF'].shift(1) >= df['DEA'].shift(1)), 'Signal'] = -1

# 持倉
df['Position'] = df['Signal'].replace(0, np.nan).ffill()
df['Position'] = df['Position'].clip(lower=0)
df['Position'] = df['Position'].shift(1)

# 報酬
df['returns'] = df['Close'].pct_change()
df['strategy'] = df['Position'] * df['returns']

# 最後才清
df = df.dropna()

df['equity_B'] = (1 + df['strategy']).cumprod()


plt.figure(figsize=(12,6))

#plt.plot(df['equity_A'], label='Wrong (dropna early)')
plt.plot(df['equity_B'], label='Correct (dropna late)')

plt.legend()
plt.grid()
plt.title("Dropna Timing Comparison")
plt.show()
