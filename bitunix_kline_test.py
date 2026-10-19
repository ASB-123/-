import requests

res = requests.get(
    "https://fapi.bitunix.com/api/v1/futures/market/kline",
    params={
        "symbol"  : "BTCUSDT",
        "interval": "1h",
        "limit"   : 200,
        "endTime" : 1781384400000  
    }
)
data = res.json().get("data", [])
print(len(data))
if data:
    print(data[0])
    print(data[-1])