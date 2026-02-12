from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.dashboard import Invoice, InvoiceResponse
from app.repositories.csv_repository import CSVRepository
from app.repositories.csv_metadata_repository import CSVMetadataRepository
from app.services.llm_service import extract_invoices_from_data
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _filter_data_by_metadata(full_data: list, metadata: list) -> list:
    """
    Filter dataset to only include columns marked as target or helper fields.
    """
    if not full_data or not metadata:
        return full_data
    
    relevant_columns = {
        meta["column_name"] 
        for meta in metadata 
        if meta.get("is_target") or meta.get("is_helper")
    }
    
    if not relevant_columns:
        return full_data
    
    filtered_data = []
    for row in full_data:
        filtered_row = {
            col: value 
            for col, value in row.items() 
            if col in relevant_columns
        }
        if filtered_row:
            filtered_data.append(filtered_row)
    
    return filtered_data


@router.get("", response_model=InvoiceResponse)
async def read_invoices(
    db: Session = Depends(get_db), 
    skip: int = 0, 
    limit: int = 50,
    status: Optional[str] = Query(None, description="Filter by invoice status (e.g., 'Overdue', 'Paid')")
):
    """
    Extract invoices from uploaded CSV documents using AI analysis.
    Analyzes all uploaded files to identify and extract invoice records.
    """
    try:
        # Fetch all documents with full data
        documents = await CSVRepository.list_documents_with_full_data()
        
        if not documents:
            return InvoiceResponse(items=[], total=0, page=1, limit=limit)
        
        document_ids = [doc.id for doc in documents]
        metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

        # Build dataset in the same format as other endpoints
        dataset = {
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "row_count": doc.row_count,
                    "column_count": doc.column_count,
                    "upload_date": str(doc.upload_date),
                    "full_data": _filter_data_by_metadata(
                        doc.full_data or [],
                        [
                            {
                                "column_name": meta.column_name,
                                "data_type": meta.data_type,
                                "connection_key": meta.connection_key,
                                "alias": meta.alias,
                                "description": meta.description,
                                "is_target": meta.is_target,
                                "is_helper": meta.is_helper,
                            }
                            for meta in metadata_by_doc.get(doc.id, [])
                        ]
                    ),
                    "metadata": [
                        {
                            "column_name": meta.column_name,
                            "data_type": meta.data_type,
                            "connection_key": meta.connection_key,
                            "alias": meta.alias,
                            "description": meta.description,
                            "is_target": meta.is_target,
                            "is_helper": meta.is_helper,
                        }
                        for meta in metadata_by_doc.get(doc.id, [])
                        if meta.is_target or meta.is_helper
                    ],
                }
                for doc in documents
            ]
        }

        # Extract invoices from the dataset using LLM
        all_invoices = extract_invoices_from_data(dataset)
        
        logger.info(f"Extracted {len(all_invoices)} invoices from uploaded data")
        print(f"Extracted {len(all_invoices)} invoices from uploaded data", flush=True)

        # Filter by status if provided
        if status:
            filtered_invoices = [
                inv for inv in all_invoices 
                if status.lower() in inv["status"].lower()
            ]
        else:
            filtered_invoices = all_invoices

        # Get total count
        total = len(filtered_invoices)

        # Apply pagination
        paginated_invoices = filtered_invoices[skip : skip + limit]

        # Convert to Invoice schema
        items = [
            Invoice(
                id=inv["id"],
                customer=inv["customer"],
                amount=inv["amount"],
                dueDate=inv["dueDate"],
                status=inv["status"],
                riskScore=inv["riskScore"],
                aiPrediction=inv["aiPrediction"]
            )
            for inv in paginated_invoices
        ]

        return InvoiceResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Error extracting invoices: {e}")
        print(f"Error extracting invoices: {e}", flush=True)
        return InvoiceResponse(items=[], total=0, page=1, limit=limit)

