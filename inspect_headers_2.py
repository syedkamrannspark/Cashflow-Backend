
import pandas as pd
import os

files = [
    'xlsx/Electricity Provider Bank Statements.xlsx',
    'xlsx/Electricity Provider Customer Payments Forecast.xlsx'
]

for file_path in files:
    print(f"\n{'='*20} {os.path.basename(file_path)} {'='*20}")
    try:
        if 'Bank Statements' in file_path:
            # Skip first 10 rows to see what's below
            df = pd.read_excel(file_path, header=None, skiprows=10, nrows=20)
        else:
            df = pd.read_excel(file_path, nrows=10) # default read
            
        print(df.to_string())
    except Exception as e:
        print(f"Error: {e}")
