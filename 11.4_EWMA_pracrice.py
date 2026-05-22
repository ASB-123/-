"""
    就只是樸實無華的把VOlume做ema
"""
import yfinance as yf
import pandas as pd

df = yf.download("ETH-USD", interval= '5m', period= '60d')
df.columns = df.columns.get_level_values(0)

df['ewma'] = df['Volume'].ewm(span= 120, adjust= False).mean()

df['trigger'] = df['ewma'] * 1.8

df['spike'] = (df['Volume'] >= df['limit']) & (df['Volume'] > 0)

print(df)