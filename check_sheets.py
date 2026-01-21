
import pandas as pd
import glob
import os

xlsx_dir = 'xlsx/'
files = glob.glob(os.path.join(xlsx_dir, '*.xlsx'))

for file_path in files:
    try:
        xl = pd.ExcelFile(file_path)
        print(f"\nFile: {os.path.basename(file_path)}")
        print(f"Sheets: {xl.sheet_names}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
