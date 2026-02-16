import asyncio
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.services.csv_service import CSVService
from app.models.csv_document import CSVDocument
from app.models.csv_metadata import CSVMetadata
from app.repositories.csv_repository import CSVRepository

async def backfill_metadata():
    print("Starting metadata backfill...")
    db = SessionLocal()
    
    try:
        # Get all documents
        documents = db.query(CSVDocument).all()
        print(f"Found {len(documents)} documents.")
        
        for doc in documents:
            # Check if metadata exists
            existing_meta = db.query(CSVMetadata).filter(CSVMetadata.document_id == doc.id).first()
            if existing_meta:
                print(f"Skipping Doc ID {doc.id} ({doc.filename}): Metadata exists.")
                continue
            
            print(f"Processing Doc ID {doc.id} ({doc.filename})...")
            
            if not doc.full_data:
                print(f"  ⚠️ Warning: No full_data for Doc ID {doc.id}. Skipping.")
                continue
            
            # Generate metadata
            # We need to use the service method. It is async and static.
            # It expects 'document' object (which connects to id) and 'full_data' list.
            
            try:
                await CSVService._generate_metadata(doc, doc.full_data)
                print(f"  ✅ Metadata generated for Doc ID {doc.id}")
            except Exception as e:
                print(f"  ❌ Failed to generate metadata for Doc ID {doc.id}: {e}")
                
    except Exception as e:
        print(f"Critical error: {e}")
    finally:
        db.close()
    
    print("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(backfill_metadata())
