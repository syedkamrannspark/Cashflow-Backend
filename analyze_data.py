
import pandas as pd
import os
import glob

xlsx_dir = 'xlsx'
files = glob.glob(os.path.join(xlsx_dir, '*.xlsx'))

if not files:
    print(f"No xlsx files found in {xlsx_dir}")
else:
    for file_path in files:
        print(f"\n{'='*50}")
        print(f"File: {os.path.basename(file_path)}")
        print(f"{'='*50}\n")
        try:
            df = pd.read_excel(file_path)
            print("--- First 5 Rows ---")
            print(df.head().to_string())
            print("\n--- Info ---")
            print(df.info())
            print("\n--- Columns ---")
            print(df.columns.tolist())
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
