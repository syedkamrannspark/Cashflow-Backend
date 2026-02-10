from app.core.database import SessionLocal
from app.repositories.csv_repository import CSVRepository
from app.repositories.csv_metadata_repository import CSVMetadataRepository
import asyncio

async def check_data():
    db = SessionLocal()
    try:
        documents = await CSVRepository.list_documents_with_full_data()
        print(f'\nTotal documents: {len(documents)}')
        
        document_ids = [doc.id for doc in documents]
        metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)
        
        for doc in documents[:2]:  # Check first 2 docs
            print(f'\n=== Document: {doc.filename} ===')
            print(f'Rows: {doc.row_count}, Columns: {doc.column_count}')
            
            # Get metadata
            metadata = metadata_by_doc.get(doc.id, [])
            print(f'\nMetadata columns ({len(metadata)} total):')
            target_helper = [m for m in metadata if m.is_target or m.is_helper]
            print(f'Target/Helper columns: {len(target_helper)}')
            for meta in target_helper[:20]:
                print(f'  - {meta.column_name} (alias: {meta.alias}, type: {meta.data_type}, target: {meta.is_target}, helper: {meta.is_helper})')
            
            # Show sample data
            if doc.full_data and len(doc.full_data) > 0:
                print(f'\nSample row keys: {list(doc.full_data[0].keys())[:15]}')
                print(f'Total data rows: {len(doc.full_data)}')
                # Show first few values
                first_row = doc.full_data[0]
                for key in list(first_row.keys())[:5]:
                    print(f'  {key}: {first_row[key]}')
    finally:
        db.close()

asyncio.run(check_data())
