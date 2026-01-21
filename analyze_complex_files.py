
import pandas as pd
import os

files = [
    'xlsx/Electricity Provider Sales Forecast.xlsx',
    'xlsx/Electricity Provider Bank Statements.xlsx',
    'xlsx/Electricity Provider Customer Payments Forecast.xlsx',
    'xlsx/Electricity Provider Expense Forecast.xlsx'
]

def find_header_and_preview(file_path):
    print(f"\n{'='*30}\nFile: {os.path.basename(file_path)}")
    try:
        # Read the first 20 rows
        df = pd.read_excel(file_path, header=None, nrows=20)
        print("--- First 20 Rows (Raw) ---")
        print(df.to_string())
        
        # Heuristic: Identify header row (row with most non-null string values or specific keywords)
        best_header_idx = -1
        max_cols = 0
        
        for idx, row in df.iterrows():
            # Count non-null strings
            non_null_strings = row.apply(lambda x: isinstance(x, str)).sum()
            if non_null_strings > max_cols:
                max_cols = non_null_strings
                best_header_idx = idx
        
        print(f"\nPotential Header Row Index: {best_header_idx}")
        if best_header_idx != -1:
             df_preview = pd.read_excel(file_path, header=best_header_idx, nrows=5)
             print("\n--- Preview with inferred header ---")
             print(df_preview.columns.tolist())
             print(df_preview.head().to_string())

    except Exception as e:
        print(f"Error: {e}")

for f in files:
    find_header_and_preview(f)
