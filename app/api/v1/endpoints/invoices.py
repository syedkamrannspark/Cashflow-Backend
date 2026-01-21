from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.invoice import AppInvoice
from app.schemas.dashboard import Invoice, InvoiceResponse

router = APIRouter()

@router.get("/", response_model=InvoiceResponse)
def read_invoices(
    db: Session = Depends(get_db), 
    skip: int = 0, 
    limit: int = 50,
    status: Optional[str] = Query(None, description="Filter by invoice status (e.g., 'Overdue', 'Paid')")
):
    query = db.query(AppInvoice)
    
    if status:
        query = query.filter(AppInvoice.status.ilike(f"%{status}%"))
        
    total = query.count()
    invoices = query.offset(skip).limit(limit).all()
    
    items = []
    for inv in invoices:
        # Simple risk logic
        risk_score = 0
        ai_pred = "Low Risk"
        
        if inv.days_past_due > 90:
            risk_score = 90
            ai_pred = "High Risk - Severely Overdue"
        elif inv.days_past_due > 30:
            risk_score = 75
            ai_pred = "Medium Risk - Overdue"
        elif inv.days_past_due > 0:
            risk_score = 50
            ai_pred = "Low Risk - Slightly Late"
            
        items.append(Invoice(
            id=inv.invoice_number,
            customer=inv.customer_name,
            amount=inv.total_amount,
            dueDate=str(inv.due_date),
            status=inv.status,
            riskScore=risk_score,
            aiPrediction=ai_pred
        ))
        
    return InvoiceResponse(
        items=items,
        total=total,
        page=(skip // limit) + 1,
        limit=limit
    )
