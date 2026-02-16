import asyncio
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.csv_metadata import CSVMetadata

def check_metadata():
    print("Checking metadata for Doc ID 5...")
    db = SessionLocal()
    try:
        metadata = db.query(CSVMetadata).filter(CSVMetadata.document_id == 5).all()
        for m in metadata:
            print(f"Column: {m.column_name}")
            print(f"  Type: {m.data_type}")
            print(f"  Target: {m.is_target}")
            print(f"  Helper: {m.is_helper}")
            print(f"  Alias: {m.alias}")
            print("-" * 20)
    finally:
        db.close()

if __name__ == "__main__":
    check_metadata()
