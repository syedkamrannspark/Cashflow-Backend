import logging

from fastapi import APIRouter, HTTPException

from app.models.csv_metadata import CSVMetadataSaveRequest, CSVMetadataSaveResponse
from app.services.csv_metadata_service import CSVMetadataService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metadata"])


@router.post(
    "/save",
    response_model=CSVMetadataSaveResponse,
    summary="Save CSV metadata",
    description="Persist column metadata for a CSV document in csv_metadata"
)
async def save_metadata(payload: CSVMetadataSaveRequest):
    try:
        saved_count = await CSVMetadataService.save_metadata(payload)
        return CSVMetadataSaveResponse(
            success=True,
            message="Metadata saved successfully",
            saved_count=saved_count,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error saving metadata: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error while saving metadata")
