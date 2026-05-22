"""
    做出Day9但用RSI跟9ema買賣訊號(要能做空)
    且要加滑點和止損
"""
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

#抓資料
df = yf.download("ETH-USD", start= "2024-02-02", end= "2026-02-02", auto_adjust= True)
df.columns = df.columns.get_level_values(0)
#把雙層結構yfinance的資料只取一層

#RSI
delta = df['Close'].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.ewm(alpha=1/14, adjust= False).mean()
avg_loss = loss.ewm(alpha=1/14, adjust= False).mean()

df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))

#Signal Line（RSI 的 EMA9）
df['signal_line'] = df['rsi'].ewm(span= 9, adjust= False).mean()
df.dropna(inplace=True)
# 直接在原本的 df 上改，沒有建新的
# 省記憶體

#訊號
df['Signal'] = 0
df.loc[(df['rsi'] > df['signal_line']) &
       (df['rsi'].shift(1) <= df['signal_line'].shift(1)), 'Signal'] =  1
df.loc[(df['rsi'] < df['signal_line']) &
       (df['rsi'].shift(1) >= df['signal_line'].shift(1)), 'Signal'] = -1

#持倉（可做多+1 / 做空-1）
df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
#把所有的0轉成nan，讓ffill可以把前面的值填入nan裡(fillna再改前面的ffill改不到的空值)
df['Position'] = df['Position'].shift(1).fillna(0)

#反手
df['trade'] = df['Position'].diff().abs().fillna(0)

#滑點 + 手續費
fee      = 0.001
slippage = 0.0005

#報酬(收益-成本)
df['returns'] = df['Close'].pct_change().fillna(0)
df['strategy_returns'] = (
    df['Position'] * df['returns']
    - df['trade'] * (fee + slippage)
)

#資金曲線(1+1*0.1= 1.1, 1.1*0.1= 1.21以此cumprod類推)
initial_capital = 100
df['equity']   = initial_capital * (1 + df['strategy_returns']).cumprod()
df['buy_hold'] = initial_capital * (1 + df['returns']).cumprod()

#最大回撤(peak歷史最高資金值，drawdown最大回測)
df['peak']     = df['equity'].cummax()
df['drawdown'] = (df['equity'] - df['peak']) / df['peak']

#Sharpe(平均收益/波動率用標準差取)，再年化
sharpe = df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(365)

#勝率(trade_times的累加能看到交易次數)
#用groupby把資料切成
trade_times  = (df['trade'] == 1).cumsum()
trade_returns = df.groupby(trade_times)['strategy_returns'].sum()
trade_win_rate = (trade_returns > 0).mean()

#Alpha / Beta
beta  = df['strategy_returns'].cov(df['returns']) / df['returns'].var()
alpha = (df['strategy_returns'].mean() - beta * df['returns'].mean()) * 365

#印出
print("Trade_times : [trade_times]")
print(f"Final Strategy : {df['equity'].iloc[-1]:.2f}")
print(f"Final Buy&Hold : {df['buy_hold'].iloc[-1]:.2f}")
print(f"Max Drawdown   : {df['drawdown'].min():.2%}")
print(f"Sharpe Ratio   : {sharpe:.2f}")
print(f"Trade Win Rate : {trade_win_rate:.2%}")
print(f"Beta           : {beta:.3f}")
print(f"Alpha (annual) : {alpha:.6f}")

#畫圖
buy  = df[df['Signal'] ==  1]
sell = df[df['Signal'] == -1]

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))

#ETH 價格
ax1.plot(df['Close'], label='ETH Price', color='black')
ax1.scatter(buy.index,  buy['Close'],  marker='^', color='green', label='Buy',  zorder=5)
ax1.scatter(sell.index, sell['Close'], marker='v', color='red',   label='Sell', zorder=5)
ax1.legend()
ax1.set_title('ETH Price + Signals')
ax1.grid(alpha=0.3)

#RSI
ax2.plot(df['rsi'], label='RSI', color='purple')
ax2.plot(df['signal_line'], label='Signal Line', color='orange')
ax2.axhline(70, linestyle='--', color='red',   alpha=0.5, label="overbuy 70")
ax2.axhline(30, linestyle='--', color='green', alpha=0.5, label="oversell 30")
ax2.legend()
ax2.set_title('RSI + Signal Line')
ax2.grid(alpha=0.3)

#資金曲線
ax3.plot(df['equity'],   label='Strategy')
ax3.plot(df['buy_hold'], label='Buy & Hold')
ax3.legend()
ax3.set_title('Equity Curve (100u)')
ax3.grid(alpha=0.3)

plt.tight_layout(pad=4)
plt.show()
