from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException

from app.services.csv_service import CSVService

router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a single CSV file and persist document metadata."""
    try:
        document = await CSVService.upload_single_csv_file(file)
        return {
            "success": True,
            "message": "File uploaded successfully",
            "data": [document],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload-multiple")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload multiple CSV files and persist document metadata."""
    try:
        documents = await CSVService.upload_csv_files(files)
        return {
            "success": True,
            "message": "Files uploaded successfully",
            "data": documents,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/check/{filename}")
async def check_document_by_name(filename: str):
    """Check whether a document with the given filename already exists."""
    exists = await CSVService.check_file_exists_by_name(filename)
    return {"exists": exists}
