"""
    策略為用ma20跟ma100的交叉做買入賣出
    只做多
    有「買 / 賣 訊號」
    有「持倉 position」
    有「報酬 return」
    畫出「資金曲線」
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#數據
df = yf.download("ETH-USD", start= '2023-01-01', end= '2024-01-01')

#ma20/ma100的製作
df['ma20'] = df['Close'].rolling(20).mean()
df['ma100'] = df['Close'].rolling(100).mean()

#做多做空訊號
#df['Signal'] = ['1' if df['ma20']> df['ma100'] else'-1' ]，邏輯錯誤，列表不應該用單點寫法
df['Signal'] = 0

#金叉買
df.loc[
    (df['ma20'] > df['ma100']) &
    (df['ma20'].shift(1) <= df['ma100'].shift(1)),
    'Signal'
] = 1

#死叉賣
df.loc[
    (df['ma20'] < df['ma100']) &
    (df['ma20'].shift(1) >= df['ma100'].shift(1)),
    'Signal'
] = -1

df['Signal'] = df['Signal'].replace(-1, 0)

#入場條件
df['Position'] = df['Signal'].replace(0, np.nan)
df['Position'] = df['Position'].ffill().fillna(0)

# 把position下移行避免用未來資料
df['Position'] = df['Position'].shift(1)

# 是否有交易
df['trade'] = df['Position'].diff().abs()

#原始報酬跟策略報酬
df['returns'] = df['Close'].pct_change()

fee = 0.001  # 0.1%

df['strategy_returns'] = (
    df['Position'] * df['returns']
    - df['trade'] * fee
)

entry_price = df['Close'].where(df['Signal'] == 1)
entry_price = entry_price.ffill()

#初始資金
initial_capital = 100

df['returns'] = df['returns'].fillna(0)
df['strategy_returns'] = df['strategy_returns'].fillna(0)

#資金曲線
df['equity'] = initial_capital * (1 + df['strategy_returns']).cumprod()
df['buy_hold'] = initial_capital * (1 + df['returns']).cumprod()

print("Final Strategy:", df['equity'].iloc[-1])
print("Final Buy&Hold:", df['buy_hold'].iloc[-1])

win_rate = (df['strategy_returns'] > 0).mean()
print("Win rate:", win_rate)
print(df)

buy = df[df['Signal'] == 1]

#畫圖(上圖為eth使用策略的買入賣出點，下圖為策略跟買入並持有比較)
fig, (ax1, ax2) = plt.subplots(2,1, figsize= (12,8))

ax1.plot(df['Close'], label='Price')
ax1.scatter(buy.index, buy['Close'], marker='^', label='Buy', color= 'green')
ax1.legend()
ax1.set_title('Buy / Sell Signals')
ax1.grid(alpha=0.3)

ax2.plot(df['equity'], label='Strategy')
ax2.plot(df['buy_hold'], label='Buy & Hold')
ax2.legend()
ax2.set_title('Equity Curve (100u)')
ax2.grid(alpha=0.3)

plt.tight_layout(pad= 3)
plt.show()
