import requests
#發送HTTP請求
import time
#API需要毫秒timestamp
import pandas as pd

url = "https://fapi.bitunix.com/api/v1/futures/market/kline"

params = {
    "symbol": "BTCUSDT",
    "interval": "15m",
    "startTime": int(time.time()*1000) - 3600*1000,
    "endTime": int(time.time()*1000)
}

"""
    參數設定:
        time.time()回傳現在時間（秒）
        *1000 = 轉成「毫秒」
        3600*1000  3600 秒 = 1 小時
        = 現在時間 - 1hr
"""
res = requests.get(url, params=params)
#發送http請求

data = res.json()
#回傳的json字串轉成python

df = pd.DataFrame(data["data"])
#轉成dataframe

print(df)