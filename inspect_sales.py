
import pandas as pd

file_path = 'xlsx/Electricity Provider Sales Forecast.xlsx'
try:
    df = pd.read_excel(file_path)
    print(f"File: {file_path}")
    print("--- First 30 rows ---")
    print(df.iloc[0:30].to_string())
except Exception as e:
    print(e)
