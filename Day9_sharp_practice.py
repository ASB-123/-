"""
    用Day8的策略去計算夏普/報酬率/
"""
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#數據導入
df = yf.download('ETH-USD', start= '2023-01-01', end= '2026-01-01', auto_adjust= True)

#ema12/ema26計算
df['ema12'] = df['Close'].ewm(span= 12, adjust= False).mean()
df['ema26'] = df['Close'].ewm(span= 26, adjust= False).mean()

#製作快線DIF
df['DIF'] = df['ema12'] - df['ema26']

#製作慢線DEA(快線抓去做9ema)
df['DEA'] = df['DIF'].ewm(span= 9, adjust= False).mean()

#把nan數據給處理掉
#df = df.dropna()

#柱狀(快-慢）
df['Hist'] = df['DIF'] - df['DEA']

#訊號(金叉為+1, 死叉為-1)
df['Signal'] = 0
#loc為用條件選取，然後改值
df.loc[(df['DIF'] > df['DEA']) & (df['DIF'].shift(1) <= df['DEA'].shift(1)), 'Signal'] =  1
df.loc[(df['DIF'] < df['DEA']) & (df['DIF'].shift(1) >= df['DEA'].shift(1)), 'Signal'] = -1

# 開倉：ffill 後 clip, 只做多
#把nan全部replace成0
df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
df['Position'] = df['Position'].clip(lower=0) 
df['Position'] = df['Position'].shift(1).fillna(0)

df['trade'] = df['Position'].diff().abs().fillna(0)
# 報酬計算
fee = 0.001
df['returns'] = df['Close'].pct_change().fillna(0)
df['strategy_returns'] = df['Position'] * df['returns'] - df['trade'] * fee

# 資金曲線
initial_capital   = 100
df['equity']    = initial_capital * (1 + df['strategy_returns']).cumprod()
df['buy_hold']  = initial_capital * (1 + df['returns']).cumprod()

# 最大回撤
df['peak'] = df['equity'].cummax()
df['drawdown'] = (df['equity'] - df['peak']) / df['peak']

# Sharpe
sharpe = df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(365)

# 交易勝率，以「每筆交易」為單位
trade_returns = df.groupby((df['trade'] == 1).cumsum())['strategy_returns'].sum()
win_rate = (trade_returns > 0).mean()

"""
以「持倉天數」為單位計算
in_position = df['Position'] != 0
win_rate = (df.loc[in_position, 'strategy_returns'] > 0).mean()
"""

# 印出
print(f"Final Equity: {df['equity'].iloc[-1]:.2f}")
print(f"Max Drawdown: {df['drawdown'].min():.2%}")
print(f"Sharpe Ratio: {sharpe:.2f}")
print(f"Win Rate: {win_rate:.2%}")

# 統計
#f:.2f,為顯示小數點後2位
print(f"Final Strategy : {df['equity'].iloc[-1]:.2f}")
print(f"Final Buy&Hold : {df['buy_hold'].iloc[-1]:.2f}")

#畫圖
buy = df[df['Signal'] == 1]

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 8))

#圖1為eth的行情及買入點
ax1.plot(df['Close'], label= 'ETH-Price', color= 'black')
ax1.scatter(buy.index, buy['Close'], marker='^', color='green', label='Buy', zorder=5)
ax1.legend()
ax1.set_title("ETH_Signal")
ax1.grid(alpha= 0.3)

#圖2為macd
ax2.plot(df['DIF'], label= 'macd', color= 'orange')
ax2.plot(df['DEA'], label= 'Signal', color= 'blue')
ax2.bar(df.index, df['Hist'], label='Histogram', width=0.5, color=['green' if x>0 else 'red' for x in df['Hist']])
ax2.axhline(0, linestyle= "--", color= "gray", alpha= 0.3)
ax2.legend()
ax2.set_title("MACD")
ax2.grid(alpha= 0.3)

#圖3為收益
ax3.plot(df['equity'],   label='Strategy')
ax3.plot(df['buy_hold'], label='Buy & Hold')
ax3.legend()
ax3.set_title('Equity Curve 100u')
ax3.grid(alpha=0.3)

plt.tight_layout(pad= 4)
plt.show()
