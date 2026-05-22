"""
    測IQR四分位距
"""
import yfinance as yf
import pandas as pd
import numpy as np

df = yf.download('ETH-USD', interval= '5m', period= '60d')
df.columns = df.columns.get_level_values(0)

roll = df['Volume'].rolling(120)

df['Q1'] = roll.quantile(0.25)
df['Q3'] = roll.quantile(0.75)
df['IQR'] = df['Q3'] - df['Q1']
df['trigger'] = df['Q3'] + 1.5 * df['IQR']

df['spike'] = df['Volume'] >= df['trigger']

print(df['spike'])
