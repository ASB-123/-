"""
    10的延續，但加入rsi要小於30/大於70才能開倉
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = yf.download("ETH-USD", interval="5m", period="60d", auto_adjust=True)
df.columns = df.columns.get_level_values(0)

delta = df['Close'].diff()
gain  = delta.clip(lower=0)
loss  = -delta.clip(upper=0)
roll = df['Volume'].rolling(120)

df["Avg_gain"] = gain.ewm(alpha=1/14, adjust=False).mean()
df["Avg_loss"] = loss.ewm(alpha=1/14, adjust=False).mean()

df['rsi'] = 100 - (100 / (1 + df['Avg_gain'] / df['Avg_loss']))
df['signal_line'] = df['rsi'].ewm(alpha=1/9, adjust=False).mean()
df['Z_score'] = (df['Volume'] - roll.mean()) / roll.std()
df['spike'] = df['Z_score'] >= 2.0

df.dropna(inplace=True)

df['signal'] = 0

#把布林值轉成字串
df['spike'] = df['spike'].map({False: 0, True: 1}).astype(int)

df.loc[
    (df['rsi'] > df['signal_line']) &
    (df['rsi'].shift(1) <= df['signal_line'].shift(1)) &
    (df['rsi'] < 30) &
    (df['spike'] == 1),
    'signal'
] = 1

df.loc[
    (df['rsi'] < df['signal_line']) &
    (df['rsi'].shift(1) >= df['signal_line'].shift(1)) &
    (df['rsi'].shift(1) > 70) &
    (df['spike'] == 1),
    'signal'
] = -1

df['Position'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
df['Position'] = df['Position'].shift(1).fillna(0)

df['trade'] = df['Position'].diff().abs().fillna(0)

fee      = 0.001
slippage = 0.0005

df['returns'] = df['Close'].pct_change().fillna(0)
df['strategy_returns'] = (
    df['Position'] * df['returns']
    - df['trade'] * (fee + slippage)
)

initial_capital = 100
df['equity']   = initial_capital * (1 + df['strategy_returns']).cumprod()
df['buy_hold'] = initial_capital * (1 + df['returns']).cumprod()

df['peak']     = df['equity'].cummax()
df['drawdown'] = (df['equity'] - df['peak']) / df['peak']

bars_per_year = 4 * 24 * 365
sharpe = df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(bars_per_year)

trade_times   = (df['trade'] > 0).cumsum()
trade_returns = df.groupby(trade_times)['strategy_returns'].sum()
trade_win_rate = (trade_returns > 0).mean()

beta  = df['strategy_returns'].cov(df['returns']) / df['returns'].var()
alpha = (df['strategy_returns'].mean() - beta * df['returns'].mean()) * bars_per_year

print(f"Trade_times    : {len(trade_returns)}")
print(f"Final Strategy : {df['equity'].iloc[-1]:.2f}")
print(f"Final Buy&Hold : {df['buy_hold'].iloc[-1]:.2f}")
print(f"Max Drawdown   : {df['drawdown'].min():.2%}")
print(f"Sharpe Ratio   : {sharpe:.2f}")
print(f"Trade Win Rate : {trade_win_rate:.2%}")
print(f"Beta           : {beta:.3f}")
print(f"Alpha (annual) : {alpha:.6f}")

buy  = df[df['signal'] ==  1]
sell = df[df['signal'] == -1]

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))

ax1.plot(df['Close'], label='ETH Price', color='black')
ax1.scatter(buy.index,  buy['Close'],  marker='^', color='green', label='Buy',  zorder=5)
ax1.scatter(sell.index, sell['Close'], marker='v', color='red',   label='Sell', zorder=5)
ax1.legend()
ax1.set_title('ETH Price + Signals')
ax1.grid(alpha=0.3)

ax2.plot(df['rsi'], label='RSI', color='purple')
ax2.plot(df['signal_line'], label='Signal Line', color='orange')
ax2.axhline(70, linestyle='--', color='red', alpha=0.5, label='Overbought 70')
ax2.axhline(30, linestyle='--', color='green', alpha=0.5, label='Oversold 30')
ax2.legend()
ax2.set_title('RSI + Signal Line')
ax2.grid(alpha=0.3)

ax3.plot(df['equity'],   label='Strategy')
ax3.plot(df['buy_hold'], label='Buy & Hold')
ax3.legend()
ax3.set_title('Equity Curve (100u)')
ax3.grid(alpha=0.3)

plt.tight_layout(pad=4)
plt.show()