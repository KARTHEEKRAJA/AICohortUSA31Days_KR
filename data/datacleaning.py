import pandas as pd

plans = pd.read_csv("D:\\31 days challenge\\data\\plans.csv")
claims = pd.read_csv("D:\\31 days challenge\\data\\claims.csv")

# Inspect
print(claims.info())
print(claims.isnull().sum())