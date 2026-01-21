
import pandas as pd
import glob
import os

xlsx_dir = 'xlsx'
files = glob.glob(os.path.join(xlsx_dir, '*.xlsx'))

for file_path in files:
    print(f"\nFile: {os.path.basename(file_path)}")
    try:
        df = pd.read_excel(file_path, nrows=0) # Read header only
        print(f"Columns: {list(df.columns)}")
    except Exception as e:
        print(f"Error: {e}")
