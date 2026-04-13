"""
RSI (Relative Strength Index)

RSI 用來衡量市場動能，核心在於 RS（Relative Strength）,也就是多頭與空頭力量的相對強弱。

首先定義多空力量：
avg_gain = 最近一段時間的平均上漲幅度
avg_loss = 最近一段時間的平均下跌幅度

接著計算：
rs = avg_gain / avg_loss

由於 rs 的範圍為 0 ~ ∞，不利於判讀，
因此將其轉換為比例形式：

rs / (1 + rs) = avg_gain / (avg_gain + avg_loss)

表示「多頭在總動能中的占比」。

最後將其縮放至 0 ~ 100：

RSI = 100 * rs / (1 + rs)

"""
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

data = yf.download("BTC-USD", start= "2024-01-01", end="2026-01-01")

delta = data["Close"].diff()

gain = delta.clip(lower=0)
#只要力道，不要方向所以用-
loss = -delta.clip(upper=0)

#跟Wilder's對齊，前14筆資料用sma
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

avg_gain = avg_gain.combine_first(
    gain.ewm(alpha=1/14, adjust=False).mean()
)
avg_loss = avg_loss.combine_first(
    loss.ewm(alpha=1/14, adjust=False).mean()
)

rs = avg_gain / avg_loss

rsi = 100 * rs / (1 + rs)
data['RSI'] = rsi

#畫布範圍
fig, (ax1, ax2) = plt.subplots(2,1, figsize=(12,8))

#圖1
ax1.plot(data['Close'], label='BTC Price')
ax1.legend()
ax1.set_title("BTC")
ax1.grid(alpha= 0.3)

#圖2
ax2.plot(data['RSI'], label='RSI')
#alpha為透明度
ax2.axhline(70, linestyle='--', color= 'green', alpha=0.5)
ax2.axhline(30, linestyle='--', color= 'red', alpha=0.5)
ax2.legend()
ax2.set_title("RSI")

plt.tight_layout(pad=4.0)
plt.show()
