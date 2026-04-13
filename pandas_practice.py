import pandas as pd
data = [62000,62500,63000,63500,64000,64500,65000]
#用pandas讀取DataFrame把資料存到變數 df
df = pd.DataFrame(data, columns=["price"])
df["double"] = df["price"]*2
#df["price_change"] = df["double"] - df["price"]. 用.diff()跟自己的數據串做差值計算
df["price_change"] = df["price"].diff()
print (df)



import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
data = np.random.randint(1200,1500,100)

df = pd.DataFrame(data, columns= ["price"])

ma10 = df["price"].rolling(10).mean()
ma20 = df["price"].rolling(20).mean()

df["ma10"] = ma10
df["ma20"] = ma20

print(df)

plt.plot(df["price"], label= "price")
plt.plot(df["ma10"], label= "ma10")
plt.plot(df["ma20"], label= "ma20")
plt.show()