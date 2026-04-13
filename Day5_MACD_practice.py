"""
    macd的快線(DIF)為ema12-ema26,慢線(DEA)為DIF的ema9,柱狀為快線-慢線
"""
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

df = yf.download("BTC-USD", start= '2023-01-01', end= '2026-01-01')

#把快線用的ema都抓出來
#span跟alpha表示不同但等效，都是控制衰減係數
df['ema12'] = df['Close'].ewm(span= 12, adjust= False).mean()
df['ema26'] = df['Close'].ewm(span= 26, adjust= False).mean()

#快線
df['DIF'] = df['ema12'] - df['ema26']

#慢線=快線做ema9
df['DEA'] = df['DIF'].ewm(span= 9, adjust= False).mean()

#柱狀
df['Hist'] = df['DIF'] - df['DEA']

#畫圖
fig, (ax1, ax2) = plt.subplots(2,1, figsize=(12,8))

#圖1為BTC
ax1.plot(df['Close'], label= 'BTC  Price', color= 'black')
ax1.set_title('BTC')
ax1.grid(alpha= 0.3)
ax1.legend()

#圖2為macd
ax2.plot(df['DIF'], label= 'macd', color= 'orange')
ax2.plot(df['DEA'], label= 'signal', color= 'blue')
#bar()裡是(x軸,y軸)，這邊x軸用df.index作為時間
ax2.bar(df.index, df['Hist'], label='Histogram', width=0.5, color=['green' if x>0 else 'red' for x in df['Hist']])
ax2.axhline(0, linestyle='--', color= 'gray', alpha=0.5)
ax2.set_title('macd')
ax2.legend()

plt.tight_layout(pad= 3)
plt.show()
