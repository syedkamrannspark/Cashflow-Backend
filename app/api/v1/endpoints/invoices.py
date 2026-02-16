from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.schemas.dashboard import Invoice, InvoiceResponse
from app.repositories.csv_repository import CSVRepository
from app.repositories.csv_metadata_repository import CSVMetadataRepository
from app.services.llm_service import extract_invoices_from_data
from app.services.pandas_analytics_service import PandasAnalyticsService
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
        
        if not documents:
            return InvoiceResponse(items=[], total=0, page=1, limit=limit)
        
        # Use Pandas Service to extract invoices
        all_invoices = PandasAnalyticsService.get_invoices_data(documents)
        
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

        # Get global stats
        stats_data = PandasAnalyticsService.get_invoices_stats(documents)
        
        # Convert to Invoice schema
        items = [
            Invoice(
                id=str(inv["id"]),
                customer=str(inv["customer"]),
                amount=float(inv["amount"]),
                dueDate=str(inv["dueDate"]),
                status=str(inv["status"]),
                riskScore=int(inv["riskScore"]),
                aiPrediction=str(inv["aiPrediction"])
            )
            for inv in paginated_invoices
        ]

        from app.schemas.dashboard import InvoiceStats
        
        invoice_stats = InvoiceStats(
            totalReceivables=stats_data["totalReceivables"],
            totalAtRiskAmount=stats_data["totalAtRiskAmount"],
            collectionRate=stats_data["collectionRate"],
            activeInvoiceCount=stats_data["activeInvoiceCount"],
            atRiskInvoiceCount=stats_data["atRiskInvoiceCount"]
        )

        return InvoiceResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1,
            limit=limit,
            stats=invoice_stats
        )

    except Exception as e:
        logger.error(f"Error extracting invoices: {e}")
        print(f"Error extracting invoices: {e}", flush=True)
        return InvoiceResponse(items=[], total=0, page=1, limit=limit)

