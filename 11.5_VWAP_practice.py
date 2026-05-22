"""
    VWAP練習(open+high+low)/(volume)
"""
import yfinance as yf
import pandas as pd

df = yf.download("ETH-USD", interval= '5m', period= '60d')
df.columns = df.columns.get_level_values(0)

df['vwap_trigger'] = (df['Open'] + df['High'] + df['Low']) / df['Volume'] * 2

df['spike'] = df['Volume'] >= df['vwap_trigger']

print(df)
