
import pandas as pd
import os

files = [
    'xlsx/Electricity Provider Sales Forecast.xlsx',
    'xlsx/Electricity Provider Bank Statements.xlsx'
]

for file_path in files:
    print(f"\n{'='*20} {os.path.basename(file_path)} {'='*20}")
    try:
        df = pd.read_excel(file_path, header=None, nrows=10)
        print(df.to_string())
    except Exception as e:
        print(f"Error: {e}")
