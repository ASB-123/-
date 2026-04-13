import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf

#data = [62000,62500,63000,63500,64000,64500,65000])(笨方法)
#data = np.random.randint(62000,66000,100)
data = yf.download("BTC-USD",interval= "15m",period= "60d")

#s = pd.Series(data)，有這種寫法，但不能用在df上

#df = pd.DataFrame(data, columns=["Close"])已經存在，不需要再轉換
#df = data["Close"],Series輸出，下面df輸出
df = data[["Close"]].rename(columns={"Close":"price"})

ma120 = df["price"].rolling(120).mean()
ma60 = df["price"].rolling(60).mean()

df["ma120"] = ma120
df["ma60"] = ma60
df["bull"] = df["ma60"] > df["ma120"]

print(df)

plt.plot(df["price"], label = "price")
plt.plot(df["ma120"], label = "ma120")
plt.plot(df["ma60"], label = "ma60")
plt.show()