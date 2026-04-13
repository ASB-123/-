import yfinance as yf

#data = yf.download("BTC-USD",start= "2023-01-01",end= "2023-02-02", interval= "15m")___會找不到資料
data = yf.download("BTC-USD", interval= "15m",period= "60d")

print(data.head())
print(data.tail())
print(len(data))