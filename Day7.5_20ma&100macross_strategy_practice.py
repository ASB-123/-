#claude優化的，但問題還是很大
#沒在平倉的
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 數據（壓平 MultiIndex）
df = yf.download("ETH-USD", start='2023-01-01', end='2024-01-01', auto_adjust=True)
df.columns = df.columns.get_level_values(0)

# MA 計算
df['ma20']  = df['Close'].rolling(20).mean()
df['ma100'] = df['Close'].rolling(100).mean()

# 先去掉 NaN，避免垃圾數值污染後續計算
df.dropna(subset=['ma20', 'ma100'], inplace=True)

## 訊號：金叉 +1 / 死叉 -1，保留兩者
df['Signal'] = 0
df.loc[(df['ma20'] > df['ma100']) & (df['ma20'].shift(1) <= df['ma100'].shift(1)), 'Signal'] =  1
df.loc[(df['ma20'] < df['ma100']) & (df['ma20'].shift(1) >= df['ma100'].shift(1)), 'Signal'] = -1

# 持倉：ffill 後 clip，只做多
df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
df['Position'] = df['Position'].clip(lower=0)   # ← 關鍵修正
df['Position'] = df['Position'].shift(1).fillna(0)

# 換手（用來扣手續費）
df['trade'] = df['Position'].diff().abs().fillna(0)

# 報酬計算
fee = 0.001
df['returns'] = df['Close'].pct_change().fillna(0)
df['strategy_returns'] = df['Position'] * df['returns'] - df['trade'] * fee

# 資金曲線
initial_capital   = 100
df['equity']    = initial_capital * (1 + df['strategy_returns']).cumprod()
df['buy_hold']  = initial_capital * (1 + df['returns']).cumprod()

# 統計
print(f"Final Strategy : {df['equity'].iloc[-1]:.2f}")
print(f"Final Buy&Hold : {df['buy_hold'].iloc[-1]:.2f}")

in_position = df['Position'] != 0
win_rate = (df.loc[in_position, 'strategy_returns'] > 0).mean()
print(f"Win Rate (持倉日): {win_rate:.2%}")

# 畫圖
buy  = df[df['Signal'] == 1]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

ax1.plot(df['Close'], label='ETH Price')
ax1.scatter(buy.index, buy['Close'], marker='^', color='green', label='Buy', zorder=5)
ax1.legend()
ax1.set_title('Buy Signals (MA20 x MA100)')
ax1.grid(alpha=0.3)

ax2.plot(df['equity'],   label='Strategy')
ax2.plot(df['buy_hold'], label='Buy & Hold')
ax2.legend()
ax2.set_title('Equity Curve 100u')
ax2.grid(alpha=0.3)

plt.tight_layout(pad=3)
plt.show()