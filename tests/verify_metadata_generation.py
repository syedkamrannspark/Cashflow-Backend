import asyncio
import io
import os
import sys
from fastapi import UploadFile
from typing import List

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.services.csv_service import CSVService
from app.models.csv_document import CSVDocument
from app.models.csv_metadata import CSVMetadata
from sqlalchemy import text

async def test_metadata_generation():
    print("Testing metadata generation...")
    
    # create dummy csv content
    csv_content = """Date,Amount,Description,Category
2023-01-01,100.00,Test Transaction,Sales
2023-01-02,-50.00,Office Supplies,Expenses
"""
    
    # Create mock UploadFile
    filename = "test_metadata_gen.csv"
    file = UploadFile(filename=filename, file=io.BytesIO(csv_content.encode('utf-8')))
    
    # Clear existing file if any
    db = SessionLocal()
    try:
        # Delete document if exists (cascade delete should handle metadata)
        existing_doc = db.query(CSVDocument).filter(CSVDocument.filename == filename).first()
        if existing_doc:
            # Manually delete metadata first just in case
            db.query(CSVMetadata).filter(CSVMetadata.document_id == existing_doc.id).delete()
            db.delete(existing_doc)
            db.commit()
            print(f"Cleaned up existing {filename}")
    except Exception as e:
        print(f"Error cleanup: {e}")
    finally:
        db.close()

    # Upload file
    try:
        print("Uploading file...")
        result = await CSVService.upload_single_csv_file(file)
        doc_id = result[0].id
        print(f"File uploaded. Document ID: {doc_id}")
        
        # Verify metadata
        db = SessionLocal()
        metadata = db.query(CSVMetadata).filter(CSVMetadata.document_id == doc_id).all()
        
        print(f"Found {len(metadata)} metadata entries.")
        
        expected_meta = {
            "Date": {"type": "date", "is_target": True},
            "Amount": {"type": "numeric", "is_target": True},
            "Description": {"type": "string", "is_target": False},
            "Category": {"type": "string", "is_helper": True}
        }
        
        for m in metadata:
            print(f"  - {m.column_name}: {m.data_type}, Target={m.is_target}, Helper={m.is_helper}")
            
            if m.column_name in expected_meta:
                 exp = expected_meta[m.column_name]
                 if m.is_target == exp.get("is_target", False) and \
                    m.is_helper == exp.get("is_helper", False):
                     print(f"    ✅ {m.column_name} matches expectations")
                 else:
                     print(f"    ❌ {m.column_name} mismatch expectations")
            
        db.close()
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_metadata_generation())
