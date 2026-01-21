
import pandas as pd
file_path = 'xlsx/Electricity Provider Bank Statements.xlsx'
df = pd.read_excel(file_path)
for i in range(20):
    print(f"Row {i}: {df.iloc[i].tolist()}")
