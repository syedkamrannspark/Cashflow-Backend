from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from typing import List
from app.services.csv_service import CSVService
from app.models.csv_document import (
    UploadResponse, 
    CSVDocumentDetail, 
    CSVDocumentList, 
    ErrorResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["CSV Management"])

@router.post(
    "/upload-single",
    response_model=UploadResponse,
    summary="Upload Single File (CSV or Excel)",
    description="Upload a single CSV or Excel file. For Excel files, each sheet will be saved as a separate document."
)
async def upload_single_csv_file(
    file: UploadFile = File(..., description="Single CSV or Excel file to upload (max 200MB)")
):
    """
    Upload a single CSV/Excel file and return preview data.
    
    - **file**: Single CSV or Excel file to upload
    - Returns: List of uploaded documents (one per sheet for Excel) with preview data
    """
    try:
        if not file or file.filename == '':
            raise HTTPException(status_code=400, detail="No file provided")
        
        results = await CSVService.upload_single_csv_file(file)
        
        return UploadResponse(
            success=True,
            data=results,
            message=f"Successfully uploaded {len(results)} document(s)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in single upload endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during file upload")

@router.post(
    "/upload-multiple",
    response_model=UploadResponse,
    summary="Upload Multiple Files (CSV or Excel)",
    description="Upload multiple CSV or Excel files. For Excel files, each sheet will be saved as a separate document."
)
async def upload_multiple_csv_files(
    files: List[UploadFile] = File(..., description="Multiple CSV or Excel files to upload (max 200MB each)")
):
    """
    Upload multiple CSV/Excel files and return preview data.
    
    - **files**: List of CSV or Excel files to upload
    - Returns: List of all created documents with preview data
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate that at least one file is provided
        if len(files) == 1 and files[0].filename == '':
            raise HTTPException(status_code=400, detail="No files selected")
        
        if len(files) == 1:
            raise HTTPException(status_code=400, detail="Use /upload-single endpoint for single file uploads")
        
        results = await CSVService.upload_csv_files(files)
        
        return UploadResponse(
            success=True,
            data=results,
            message=f"Successfully uploaded {len(results)} files"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in multiple upload endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during file upload")

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload CSV Files (Deprecated)",
    description="⚠️ DEPRECATED: Use /upload-single for single file or /upload-multiple for multiple files",
    deprecated=True
)
async def upload_csv_files_deprecated(
    files: List[UploadFile] = File(..., description="CSV files to upload (max 200MB each)")
):
    """
    ⚠️ DEPRECATED: This endpoint is deprecated. Please use:
    - /upload-single for single file uploads
    - /upload-multiple for multiple file uploads
    
    Upload CSV files and return preview data.
    
    - **files**: List of CSV files to upload
    - Returns: List of uploaded documents with preview data
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Validate that at least one file is provided
        if len(files) == 1 and files[0].filename == '':
            raise HTTPException(status_code=400, detail="No files selected")
        
        # Route to appropriate new endpoint based on file count
        if len(files) == 1:
            results = await CSVService.upload_single_csv_file(files[0])
            return UploadResponse(
                success=True,
                data=results,
                message=f"Successfully uploaded {len(results)} document(s) (consider using /upload-single endpoint)"
            )
        else:
            results = await CSVService.upload_csv_files(files)
            return UploadResponse(
                success=True,
                data=results,
                message=f"Successfully uploaded {len(results)} files (consider using /upload-multiple endpoint)"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in deprecated upload endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during file upload")

@router.get(
    "/",
    response_model=List[CSVDocumentList],
    summary="List All Documents",
    description="Get a paginated list of all uploaded CSV documents"
)
async def list_documents(
    limit: int = Query(100, description="Maximum number of documents to return", ge=1, le=1000),
    offset: int = Query(0, description="Number of documents to skip", ge=0)
):
    """
    List all uploaded documents with pagination.
    
    - **limit**: Maximum number of documents to return (1-1000)
    - **offset**: Number of documents to skip for pagination
    - Returns: List of document metadata
    """
    try:
        documents = await CSVService.list_documents(limit, offset)
        return documents
        
    except Exception as e:
        logger.error(f"Unexpected error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while listing documents")

@router.patch(
    "/{document_id}/description-status",
    summary="Update Description Status",
    description="Update the description status of a document"
)
async def update_description_status(
    document_id: int,
    is_described: bool = Query(..., description="New description status")
):
    """
    Update document description status.
    
    - **document_id**: ID of the document to update
    - **is_described**: New description status
    - Returns: Success confirmation
    """
    try:
        success = await CSVService.update_document_description_status(document_id, is_described)
        return {"success": True, "message": "Description status updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while updating document")

@router.delete(
    "/{document_id}",
    summary="Delete Document",
    description="Delete a CSV document from the database"
)
async def delete_document(document_id: int):
    """
    Delete a CSV document.
    
    - **document_id**: ID of the document to delete
    - Returns: Success confirmation
    """
    try:
        success = await CSVService.delete_document(document_id)
        return {"success": True, "message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while deleting document")

@router.get(
    "/check-by-name",
    summary="Check if file is already uploaded by name",
    description="Check whether a CSV file with the given filename has already been uploaded.",
)
async def check_document_by_name(
    filename: str = Query(..., description="Filename to check (including extension)")
):
    """Return whether a document with the given filename already exists"""
    try:
        exists = await CSVService.check_file_exists_by_name(filename)
        return {"exists": exists}
    
    except Exception as e:
        logger.error(f"Unexpected error checking document by name '{filename}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error while checking document by name")

@router.get(
    "/{document_id}",
    response_model=CSVDocumentDetail,
    summary="Get Document by ID",
    description="Fetch a specific CSV document by ID with preview or full data"
)
async def get_document(
    document_id: int,
    include_full_data: bool = Query(False, description="Include full CSV data in response")
):
    """
    Fetch CSV document by ID.
    
    - **id**: Document ID to fetch
    - **include_full_data**: Whether to include full CSV data (default: false, only preview)
    - Returns: Document with preview or full data
    """
    try:
        document = await CSVService.get_document_by_id(document_id, include_full_data)
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching document")