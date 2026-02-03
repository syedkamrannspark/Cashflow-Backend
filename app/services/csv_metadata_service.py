from fastapi import HTTPException

from app.models.csv_metadata import CSVMetadataSaveRequest
from app.repositories.csv_metadata_repository import CSVMetadataRepository
from app.repositories.csv_repository import CSVRepository


class CSVMetadataService:
    @staticmethod
    async def save_metadata(payload: CSVMetadataSaveRequest) -> int:
        document = await CSVRepository.get_document_preview_by_id(payload.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        if not payload.columns:
            raise HTTPException(status_code=400, detail="No metadata columns provided")
        saved_count = await CSVMetadataRepository.replace_metadata(payload.document_id, payload.columns)
        
        # Mark document as described/mapped
        await CSVRepository.update_document_description_status(payload.document_id, True)
        
        return saved_count
