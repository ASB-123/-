"""
    Median Absolute Deviation(MAD)測試
"""
import yfinance as yf
import pandas as pd
import numpy as np

df = yf.download('ETH-USD', interval= '5m', period= '60d')
df.columns = df.columns.get_level_values(0)

df['Q2'] = df['Volume'].rolling(120).quantile(0.50)

df['MAD'] = (df['Volume'] - df['Q2']).abs().rolling(120).quantile(0.50)

df["MAD_score"] = (df['Volume'] - df['Q2']) / (1.4826 * df['MAD'])

df['spike'] = df["MAD_score"] >= 3.5

print(df['spike'])

