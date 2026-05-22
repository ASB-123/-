"""
    volumespike各種方法測試,先測zscore
"""
import yfinance as yf
import pandas as pd

df = yf.download("ETH-USD", interval= '15m', period= '60d')
df.columns = df.columns.get_level_values(0)

df['avg_volume'] = df['Volume'].rolling(120).mean()
df['Z_score'] = (df['Volume'] - df['avg_volume']) / df['Volume'].rolling(120).std()

df['spike'] = df['Z_score'] >= 2.0

print(df['spike'])