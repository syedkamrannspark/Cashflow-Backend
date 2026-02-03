import pandas as pd
import io
from typing import List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException
from app.core.config import settings
from app.models.csv_document import CSVDocumentCreate, CSVDocumentResponse, CSVDocumentDetail, CSVDocumentList
from app.repositories.csv_repository import CSVRepository
import logging
import hashlib
import json
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

class CSVService:
    
    @staticmethod
    def generate_data_hash(full_data: List[Dict[str, Any]]) -> str:
        """Generate SHA256 hash of CSV data for change detection"""
        try:
            data_str = json.dumps(full_data, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate data hash: {e}")
            return "unknown"
    
    @staticmethod
    async def notify_main_brain_of_new_upload(document_id: int, filename: str) -> bool:
        """
        Notify Main Brain of new CSV upload (non-blocking, fire-and-forget)
        This triggers immediate sync instead of waiting 5 minutes
        """
        try:
            # Use localhost:8000 if in docker, or configure the URL
            main_brain_url = "http://localhost:8000/api/v1/admin/sync/trigger"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    main_brain_url,
                    json={"document_id": document_id, "filename": filename},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Main Brain notified of upload: {filename} (ID: {document_id})")
                        return True
                    else:
                        logger.warning(f"⚠️ Main Brain returned status {response.status}")
                        return False
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout notifying Main Brain for {filename}")
            return False
        except Exception as e:
            # Don't fail the upload if notification fails - this is just a nice-to-have
            logger.warning(f"⚠️ Could not notify Main Brain of upload '{filename}': {e}")
            return False
    

    @staticmethod
    def validate_file(file: UploadFile) -> None:
        """Validate uploaded file"""
        # Check file extension
        if not any(file.filename.lower().endswith(ext) for ext in settings.allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Only {', '.join(settings.allowed_extensions)} files are allowed."
            )
        
        # File size validation will be handled by FastAPI's File size limit
        
    @staticmethod
    async def parse_csv_content(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
        """Parse CSV content and return preview, full data, and metadata"""
        try:
            # Decode content
            csv_string = content.decode('utf-8')
            
            # Parse CSV with pandas
            df = pd.read_csv(io.StringIO(csv_string))
            
            if df.empty:
                raise HTTPException(status_code=400, detail=f"File {filename} is empty")
            
            # Handle NaN values by converting to None for JSON serialization
            df = df.where(pd.notnull(df), None)
            
            # Get preview (first 5 rows)
            preview_df = df.head(5)
            preview_data = preview_df.to_dict('records')
            
            # Convert full dataframe to JSON
            full_data = df.to_dict('records')
            
            row_count = len(df)
            column_count = len(df.columns)
            
            return preview_data, full_data, row_count, column_count
            
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail=f"File {filename} encoding is not supported. Please use UTF-8.")
        except pd.errors.EmptyDataError:
            raise HTTPException(status_code=400, detail=f"File {filename} is empty or invalid")
        except pd.errors.ParserError as e:
            raise HTTPException(status_code=400, detail=f"Error parsing {filename}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error parsing {filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing {filename}: {str(e)}")

    @staticmethod
    async def is_filename_already_uploaded(filename: str) -> bool:
        """Return True if a document with the given filename already exists"""
        return await CSVRepository.document_exists_by_filename(filename)
    
    @staticmethod
    async def upload_csv_files(files: List[UploadFile]) -> List[CSVDocumentResponse]:
        """Process and upload multiple CSV files"""
        results = []
        
        for file in files:
            try:
                # Validate file
                CSVService.validate_file(file)

                # Check for duplicate filename before processing
                if await CSVService.is_filename_already_uploaded(file.filename):
                    raise HTTPException(
                        status_code=409,
                        detail=f"File '{file.filename}' has already been uploaded"
                    )
                
                # Check file size
                content = await file.read()
                if len(content) > settings.max_file_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File {file.filename} exceeds maximum size of {settings.max_file_size / (1024*1024):.0f}MB"
                    )
                
                # Parse CSV content
                preview_data, full_data, row_count, column_count = await CSVService.parse_csv_content(
                    content, file.filename
                )
                
                # Create document data
                document_data = CSVDocumentCreate(
                    filename=file.filename,
                    preview_data=preview_data,
                    full_data=full_data,
                    row_count=row_count,
                    column_count=column_count
                )
                
                # Save to database
                document = await CSVRepository.create_document(document_data)
                if document:
                    results.append(document)
                    
                    # 🔔 Notify Main Brain of new upload (non-blocking)
                    # This triggers immediate sync instead of waiting 5 minutes
                    asyncio.create_task(
                        CSVService.notify_main_brain_of_new_upload(document.id, document.filename)
                    )
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to save {file.filename} to database")
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Unexpected error processing {file.filename}: {e}")
                raise HTTPException(status_code=500, detail=f"Error processing {file.filename}: {str(e)}")
        
        return results
    
    @staticmethod
    async def upload_single_csv_file(file: UploadFile) -> CSVDocumentResponse:
        """Process and upload a single CSV file"""
        try:
            # Validate file
            CSVService.validate_file(file)

            # Check for duplicate filename before processing
            if await CSVService.is_filename_already_uploaded(file.filename):
                raise HTTPException(
                    status_code=409,
                    detail=f"File '{file.filename}' has already been uploaded"
                )
            
            # Check file size
            content = await file.read()
            if len(content) > settings.max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File {file.filename} exceeds maximum size of {settings.max_file_size / (1024*1024):.0f}MB"
                )
            
            # Parse CSV content
            preview_data, full_data, row_count, column_count = await CSVService.parse_csv_content(
                content, file.filename
            )
            print(full_data, "full_data")
            # Create document data
            document_data = CSVDocumentCreate(
                filename=file.filename,
                preview_data=preview_data,
                full_data=full_data,
                row_count=row_count,
                column_count=column_count
            )
            
            # Save to database
            document = await CSVRepository.create_document(document_data)
            if document:
                # 🔔 Notify Main Brain of new upload (non-blocking)
                # This triggers immediate sync instead of waiting 5 minutes
                asyncio.create_task(
                    CSVService.notify_main_brain_of_new_upload(document.id, document.filename)
                )
                return document
            else:
                raise HTTPException(status_code=500, detail=f"Failed to save {file.filename} to database")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing {file.filename}: {str(e)}")
    
    @staticmethod
    async def get_document_by_id(document_id: int, include_full_data: bool = False) -> CSVDocumentDetail:
        """Get document by ID"""
        if include_full_data:
            document = await CSVRepository.get_document_by_id(document_id)
        else:
            document = await CSVRepository.get_document_preview_by_id(document_id)
            # Convert to CSVDocumentDetail for consistent return type
            if document:
                document = CSVDocumentDetail(
                    id=document.id,
                    filename=document.filename,
                    preview=document.preview,
                    is_described=document.is_described,
                    row_count=document.row_count,
                    column_count=document.column_count,
                    upload_date=document.upload_date,
                    full_data=None
                )
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return document
    
    @staticmethod
    async def list_documents(limit: int = 100, offset: int = 0) -> List[CSVDocumentList]:
        """List all documents with pagination"""
        return await CSVRepository.list_documents(limit, offset)
    
    @staticmethod
    async def update_document_description_status(document_id: int, is_described: bool) -> bool:
        """Update document description status"""
        success = await CSVRepository.update_document_description_status(document_id, is_described)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return success
    
    @staticmethod
    async def delete_document(document_id: int) -> bool:
        """Delete document and its associated metadata"""
        # First, delete all metadata associated with the document
        from app.repositories.csv_metadata_repository import CSVMetadataRepository
        await CSVMetadataRepository.delete_metadata_by_document_id(document_id)
        
        # Then delete the document itself
        success = await CSVRepository.delete_document(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return success

    @staticmethod
    async def check_file_exists_by_name(filename: str) -> bool:
        """Public helper to check if a file has already been uploaded by its name"""
        return await CSVRepository.document_exists_by_filename(filename)