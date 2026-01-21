
import pandas as pd
import os

files = [
    'xlsx/Electricity Provider Bank Statements.xlsx',
    'xlsx/Electricity Provider Sales Forecast.xlsx',
    'xlsx/Electricity Provider Expense Forecast.xlsx'
]

# We suspect Bank Statements might have transactions lower down.
# We suspect Forecasts might be simple monthly columns.

def inspect_deep(file_path):
    print(f"\n{'='*40}")
    print(f"File: {os.path.basename(file_path)}")
    print(f"{'='*40}")
    
    try:
        df = pd.read_excel(file_path)
        # Check for keywords like "Date", "Description", "Amount", "Month", "Jan"
        # Print locations of potential headers
        
        print("\n--- Searching for 'Date' column ---")
        # Find row/col where value is 'Date' or 'Transaction Date'
        for i in range(min(50, len(df))):
            row_vals = df.iloc[i].astype(str).tolist()
            if any('date' in s.lower() for s in row_vals):
                print(f"Row {i}: {row_vals}")

        print("\n--- Searching for 'Month' or 'Jan' ---")
        for i in range(min(50, len(df))):
            row_vals = df.iloc[i].astype(str).tolist()
            if any('month' in s.lower() or 'jan' in s.lower() for s in row_vals):
                print(f"Row {i}: {row_vals}")

        # Just print row 15-25 to see if there is a structure change (e.g. after summary)
        if len(df) > 20:
             print("\n--- Rows 15-25 ---")
             print(df.iloc[15:25].to_string())
             
    except Exception as e:
        print(f"Error: {e}")

for f in files:
    inspect_deep(f)
