#函式庫輸入
import yfinance as yf
import pandas as pd
import numpy as np

#資料輸入
data = yf.download("BTC-USD", interval= "15m", period= "60d")

#資料用pandas的df再定義,不一定要這一步
df = data[["Close"]].rename(columns={"Close":"price"})

#return定義
df["return"] = df["price"].pct_change(fill_method=None)
"""
    df["ret_1"] = df["price"].pct_change()
    df["ret_4"] = df["price"].pct_change(4)
    df["ret_96"] = df["price"].pct_change(96)
"""

#刪除NaN
df = df.dropna()

print(df)
