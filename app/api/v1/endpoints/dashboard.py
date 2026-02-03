from fastapi import APIRouter, Depends
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database import get_db
from app.models.invoice import AppInvoice
from app.models.payment_history import PaymentHistory
from app.models.complex_models import ForecastMetric
from app.schemas.dashboard import CashPosition, ChartDataPoint, CashFlowDataPoint
from app.repositories.csv_repository import CSVRepository
from app.repositories.csv_metadata_repository import CSVMetadataRepository
from app.services.llm_service import get_insights, get_stats_from_openrouter, get_cash_forecast_from_openrouter, get_cash_flow_from_openrouter
import datetime
import re

def parse_currency(value: str) -> float:
    if not value or value == 'nan':
        return 0.0
    # Remove $, commas, %
    clean = re.sub(r'[^\d.-]', '', str(value))
    try:
        return float(clean)
    except:
        return 0.0

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_float(value) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        clean = re.sub(r"[^\d.-]", "", str(value))
        return float(clean) if clean not in ("", None) else 0.0
    except Exception:
        return 0.0


def _to_int(value) -> int:
    try:
        return int(round(_to_float(value)))
    except Exception:
        return 0


def _filter_data_by_metadata(full_data: list, metadata: list) -> list:
    """
    Filter dataset to only include columns marked as target or helper fields.
    Only columns with is_target=True or is_helper=True are included.
    """
    if not full_data or not metadata:
        return full_data
    
    # Get column names that are either target or helper
    relevant_columns = {
        meta["column_name"] 
        for meta in metadata 
        if meta.get("is_target") or meta.get("is_helper")
    }
    
    if not relevant_columns:
        # If no columns are marked as target/helper, return empty data
        return []
    
    # Filter each row to only include relevant columns
    filtered_data = []
    for row in full_data:
        filtered_row = {
            col: value 
            for col, value in row.items() 
            if col in relevant_columns
        }
        if filtered_row:  # Only add non-empty rows
            filtered_data.append(filtered_row)
    
    return filtered_data


@router.get("/stats", response_model=CashPosition)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    documents = await CSVRepository.list_documents_with_full_data()
    document_ids = [doc.id for doc in documents]
    metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

    dataset = {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "row_count": doc.row_count,
                "column_count": doc.column_count,
                "upload_date": doc.upload_date,
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
                    if meta.is_target or meta.is_helper  # Only include target/helper metadata
                ],
            }
            for doc in documents
        ]
    }

    print("/stats dataset:", dataset, flush=True)
    llm_stats = get_stats_from_openrouter(dataset) or {}
    logger.info("/stats OpenRouter response: %s", llm_stats)
    print("/stats OpenRouter response:", llm_stats, flush=True)

    response = CashPosition(
        current=_to_float(llm_stats.get("current")),
        forecast30Day=_to_float(llm_stats.get("forecast30Day")),
        atRiskInvoices=_to_float(llm_stats.get("atRiskInvoices")),
        cashRunway=_to_int(llm_stats.get("cashRunway")),
        currentChangePercent=_to_float(llm_stats.get("currentChangePercent")),
        forecastChangePercent=_to_float(llm_stats.get("forecastChangePercent")),
        overdueInvoicesCount=_to_int(llm_stats.get("overdueInvoicesCount")),
    )
    logger.info("/stats API response payload: %s", response.model_dump())
    print("/stats API response payload:", response.model_dump(), flush=True)
    return response

@router.get("/forecast", response_model=List[ChartDataPoint])
async def get_cash_forecast(db: Session = Depends(get_db)):
    documents = await CSVRepository.list_documents_with_full_data()
    document_ids = [doc.id for doc in documents]
    metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

    dataset = {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "row_count": doc.row_count,
                "column_count": doc.column_count,
                "upload_date": doc.upload_date,
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
                    if meta.is_target or meta.is_helper  # Only include target/helper metadata
                ],
            }
            for doc in documents
        ]
    }

    llm_points = get_cash_forecast_from_openrouter(dataset)
    logger.info("/forecast OpenRouter response: %s", llm_points)
    print("/forecast OpenRouter response:", llm_points, flush=True)

    data_points: List[ChartDataPoint] = []
    for i in range(8):
        default_date = f"Week {i + 1}"
        point = llm_points[i] if isinstance(llm_points, list) and len(llm_points) > i else {}
        data_points.append(
            ChartDataPoint(
                date=point.get("date") or default_date,
                actual=_to_float(point.get("actual")),
                forecasted=_to_float(point.get("forecasted")),
            )
        )

    print("/forecast API response payload:", [p.model_dump() for p in data_points], flush=True)
    return data_points

@router.get("/insights")
def get_dashboard_insights(db: Session = Depends(get_db)):
    # Re-use logic or call function directly if refactored. 
    # For now, duplicate logic for simplicity or refactor get_dashboard_stats to return object not Response
    
    # 1. At Risk Invoices
    at_risk_query = db.query(AppInvoice).filter(AppInvoice.days_past_due > 0)
    at_risk_amount = at_risk_query.with_entities(func.sum(AppInvoice.balance_due)).scalar() or 0
    at_risk_count = at_risk_query.count()
    
    # 2. Forecast
    today = datetime.date.today()
    next_30 = today + datetime.timedelta(days=30)
    forecast_query = db.query(AppInvoice).filter(
        AppInvoice.due_date >= today,
        AppInvoice.due_date <= next_30
    )
    forecast_amount = forecast_query.with_entities(func.sum(AppInvoice.balance_due)).scalar() or 0
    
    context = f"At Risk Amount: {at_risk_amount}, Overdue Count: {at_risk_count}, 30-Day Collection Forecast: {forecast_amount}"
    
    return {"insights": get_insights(context)}

@router.get("/flow", response_model=List[CashFlowDataPoint])
async def get_cash_flow(db: Session = Depends(get_db)):
    documents = await CSVRepository.list_documents_with_full_data()
    document_ids = [doc.id for doc in documents]
    metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

    dataset = {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "row_count": doc.row_count,
                "column_count": doc.column_count,
                "upload_date": doc.upload_date,
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
                    if meta.is_target or meta.is_helper  # Only include target/helper metadata
                ],
            }
            for doc in documents
        ]
    }

    llm_points = get_cash_flow_from_openrouter(dataset)
    logger.info("/flow OpenRouter response: %s", llm_points)
    print("/flow OpenRouter response:", llm_points, flush=True)

    result: List[CashFlowDataPoint] = []
    for i in range(4):
        default_week = f"Week {i + 1}"
        point = llm_points[i] if isinstance(llm_points, list) and len(llm_points) > i else {}
        result.append(
            CashFlowDataPoint(
                week=point.get("week") or default_week,
                inflows=_to_float(point.get("inflows")),
                outflows=_to_float(point.get("outflows")),
            )
        )

    print("/flow API response payload:", [p.model_dump() for p in result], flush=True)
    return result
