
import pandas as pd
import os

file_path = "xlsx/Electricity Provider Bank Statements.xlsx"
sheet_name = "Transaction Detail"

try:
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    print(f"Columns in {sheet_name}: {list(df.columns)}")
    print("First 5 rows:")
    print(df.head())
except Exception as e:
    print(f"Error reading {sheet_name}: {e}")
