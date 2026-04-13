import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

data = [100,101,102,103,104,105]

print("平均價格:", np.mean(data))

df = pd.DataFrame(data, columns=["price"])

df["MA3"] = df["price"].rolling(3).mean()

print(df)

plt.plot(df["price"])
plt.plot(df["MA3"])
plt.show()