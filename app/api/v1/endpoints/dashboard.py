from fastapi import APIRouter, Depends
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from app.core.database import get_db
from app.models.invoice import AppInvoice
from app.models.payment_history import PaymentHistory
from app.models.complex_models import ForecastMetric
from app.schemas.dashboard import CashPosition, ChartDataPoint, CashFlowDataPoint, QueryResponse, ChartDataSchema
from app.repositories.csv_repository import CSVRepository
from app.repositories.csv_metadata_repository import CSVMetadataRepository
from app.services.llm_service import get_insights, get_stats_from_openrouter, get_cash_forecast_from_openrouter, get_cash_flow_from_openrouter, answer_user_query, get_scenario_analysis_from_openrouter
import datetime
import re
import hashlib
import json
import time

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

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL
_cache: Dict[str, Dict[str, Any]] = {}


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


def _generate_cache_key(dataset: dict) -> str:
    """
    Generate a consistent hash key for the dataset to use as cache key.
    """
    # Sort keys to ensure consistent ordering
    serialized = json.dumps(dataset, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _get_cached_response(cache_key: str) -> Optional[Any]:
    """
    Retrieve cached response if it exists and hasn't expired.
    """
    if cache_key in _cache:
        cached_entry = _cache[cache_key]
        if time.time() - cached_entry["timestamp"] < CACHE_TTL_SECONDS:
            logger.info(f"Cache HIT for key: {cache_key[:16]}...")
            return cached_entry["data"]
        else:
            # Expired, remove from cache
            del _cache[cache_key]
            logger.info(f"Cache EXPIRED for key: {cache_key[:16]}...")
    logger.info(f"Cache MISS for key: {cache_key[:16]}...")
    return None


def _set_cached_response(cache_key: str, data: Any) -> None:
    """
    Store response in cache with current timestamp.
    """
    _cache[cache_key] = {
        "data": data,
        "timestamp": time.time()
    }
    logger.info(f"Cache SET for key: {cache_key[:16]}... (total cached items: {len(_cache)})")


def _filter_data_by_metadata(full_data: list, metadata: list) -> list:
    """
    Filter dataset to only include columns marked as target or helper fields.
    Only columns with is_target=True or is_helper=True are included.
    If no columns are marked, returns all data.
    """
    if not full_data:
        return full_data
    
    if not metadata:
        # No metadata defined, return all data
        return full_data
    
    # Get column names that are either target or helper
    relevant_columns = {
        meta["column_name"] 
        for meta in metadata 
        if meta.get("is_target") or meta.get("is_helper")
    }
    
    if not relevant_columns:
        # If no columns are marked as target/helper, return all data
        return full_data
    
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
    
    # Check cache first
    cache_key = f"stats_{_generate_cache_key(dataset)}"
    llm_stats = _get_cached_response(cache_key)
    
    if llm_stats is None:
        # Cache miss - call LLM
        llm_stats = get_stats_from_openrouter(dataset) or {}
        _set_cached_response(cache_key, llm_stats)
    
    logger.info("/stats OpenRouter response: %s", llm_stats)
    print("/stats OpenRouter response:", llm_stats, flush=True)

    # Build detailed breakdowns from LLM response
    current_breakdown = None
    forecast_breakdown = None
    atrisk_breakdown = None
    runway_breakdown = None
    
    if "currentBreakdown" in llm_stats:
        current_breakdown = llm_stats["currentBreakdown"]
    if "forecastBreakdown" in llm_stats:
        forecast_breakdown = llm_stats["forecastBreakdown"]
    if "atRiskBreakdown" in llm_stats:
        atrisk_breakdown = llm_stats["atRiskBreakdown"]
    if "runwayBreakdown" in llm_stats:
        runway_breakdown = llm_stats["runwayBreakdown"]

    response = CashPosition(
        current=_to_float(llm_stats.get("current")),
        forecast30Day=_to_float(llm_stats.get("forecast30Day")),
        atRiskInvoices=_to_float(llm_stats.get("atRiskInvoices")),
        cashRunway=_to_int(llm_stats.get("cashRunway")),
        currentChangePercent=_to_float(llm_stats.get("currentChangePercent")),
        forecastChangePercent=_to_float(llm_stats.get("forecastChangePercent")),
        overdueInvoicesCount=_to_int(llm_stats.get("overdueInvoicesCount")),
        currentBreakdown=current_breakdown,
        forecastBreakdown=forecast_breakdown,
        atRiskBreakdown=atrisk_breakdown,
        runwayBreakdown=runway_breakdown,
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

    # Check cache first
    cache_key = f"forecast_{_generate_cache_key(dataset)}"
    llm_points = _get_cached_response(cache_key)
    
    if llm_points is None:
        # Cache miss - call LLM
        llm_points = get_cash_forecast_from_openrouter(dataset)
        _set_cached_response(cache_key, llm_points)
    
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
async def get_dashboard_insights(db: Session = Depends(get_db)):
    """
    Generate AI insights based on uploaded CSV data.
    Uses data from csv_documents and csv_metadata tables.
    """
    # Fetch all documents with full data
    documents = await CSVRepository.list_documents_with_full_data()
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

    # Build context from uploaded data
    context_parts = []
    context_parts.append(f"Total uploaded files: {len(documents)}")
    
    for doc in dataset["documents"]:
        context_parts.append(f"\nFile: {doc['filename']}")
        context_parts.append(f"Rows: {doc['row_count']}, Columns: {doc['column_count']}")
        
        if doc['metadata']:
            context_parts.append("Key columns:")
            for meta in doc['metadata'][:5]:  # Show first 5 metadata columns
                context_parts.append(f"  - {meta['alias'] or meta['column_name']}: {meta['description']}")
        
        # Sample data summary
        if doc['full_data']:
            context_parts.append(f"Data sample: {len(doc['full_data'])} records available")
    
    context = "\n".join(context_parts)
    
    return {"insights": get_insights(context)}


@router.get("/scenario-analysis")
async def get_scenario_analysis(db: Session = Depends(get_db)):
    """
    Generate AI-powered scenario analysis with optimistic, expected, and pessimistic forecasts
    based on uploaded CSV data.
    """
    # Fetch all documents with full data
    documents = await CSVRepository.list_documents_with_full_data()
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

    # Check cache first
    cache_key = f"scenario_{_generate_cache_key(dataset)}"
    scenario_points = _get_cached_response(cache_key)
    
    if scenario_points is None:
        # Cache miss - call LLM
        scenario_points = get_scenario_analysis_from_openrouter(dataset)
        _set_cached_response(cache_key, scenario_points)
    
    logger.info("/scenario-analysis OpenRouter response: %s", scenario_points)
    print("/scenario-analysis OpenRouter response:", scenario_points, flush=True)

    # Return the scenario analysis points
    # Format: [{"week": "Week 1", "optimistic": 1150000, "expected": 1000000, "pessimistic": 850000}, ...]
    return scenario_points


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

    # Check cache first
    cache_key = f"flow_{_generate_cache_key(dataset)}"
    llm_points = _get_cached_response(cache_key)
    
    if llm_points is None:
        # Cache miss - call LLM
        llm_points = get_cash_flow_from_openrouter(dataset)
        _set_cached_response(cache_key, llm_points)
    
    logger.info("/flow OpenRouter response: %s", llm_points)
    print("/flow OpenRouter response:", llm_points, flush=True)

    result: List[CashFlowDataPoint] = []
    from datetime import datetime, timedelta
    for i in range(4):
        default_week = f"Week {i + 1}"
        # Calculate default date (going backwards from today)
        default_date = (datetime.now() - timedelta(days=(3 - i) * 7)).strftime("%Y-%m-%d")
        point = llm_points[i] if isinstance(llm_points, list) and len(llm_points) > i else {}
        result.append(
            CashFlowDataPoint(
                week=point.get("week") or default_week,
                date=point.get("date") or default_date,
                inflows=_to_float(point.get("inflows")),
                outflows=_to_float(point.get("outflows")),
            )
        )

    print("/flow API response payload:", [p.model_dump() for p in result], flush=True)
    return result


@router.post("/query", response_model=QueryResponse)
async def query_data_assistant(query_payload: dict, db: Session = Depends(get_db)):
    """
    Answer user queries about their uploaded data using AI.
    Supports visualization requests by detecting keywords and generating chart data.
    """
    query = query_payload.get("query", "").strip()
    
    if not query:
        return QueryResponse(response="Please enter a valid question.")
    
    # Fetch all documents with their data
    documents = await CSVRepository.list_documents_with_full_data()
    document_ids = [doc.id for doc in documents]
    metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

    # Build dataset for the LLM
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
            }
            for doc in documents
        ]
    }

    # Check if user is asking for visualization
    chart_data = _detect_and_generate_chart(query, dataset, db)
    
    # Get response from AI
    response = answer_user_query(query, dataset)
    
    # Enhance response with professional formatting
    if chart_data:
        response = _enhance_with_professional_formatting(response, chart_data)
    
    logger.info("/query response: %s", response)
    print("/query response:", response, flush=True)
    
    return QueryResponse(
        response=response,
        chartData=chart_data
    )


def _detect_and_generate_chart(query: str, dataset: dict, db: Session) -> Optional[ChartDataSchema]:
    """
    Detect if user is asking for visualization and generate appropriate chart data.
    """
    query_lower = query.lower()
    
    # Keywords that indicate visualization request
    viz_keywords = ["chart", "graph", "plot", "visualize", "show", "display", "breakdown", "distribution", "trend", "compare"]
    is_viz_request = any(keyword in query_lower for keyword in viz_keywords)
    
    if not is_viz_request:
        return None
    
    # Detect chart type
    chart_type = _detect_chart_type(query_lower)
    
    # Detect data type
    data_type = _detect_data_type(query_lower)
    
    # Generate chart data based on detected type
    if chart_type == "bar":
        return _generate_bar_chart(data_type, dataset, db)
    elif chart_type == "line":
        return _generate_line_chart(data_type, dataset, db)
    elif chart_type == "pie":
        return _generate_pie_chart(data_type, dataset, db)
    elif chart_type == "area":
        return _generate_area_chart(data_type, dataset, db)
    
    return None


def _detect_chart_type(query_lower: str) -> str:
    """Detect what type of chart is being requested"""
    if "bar" in query_lower or "compare" in query_lower or "breakdown by" in query_lower:
        return "bar"
    elif "line" in query_lower or "trend" in query_lower or "over time" in query_lower:
        return "line"
    elif "pie" in query_lower or "distribution" in query_lower or "breakdown" in query_lower:
        return "pie"
    elif "area" in query_lower or "cumulative" in query_lower or "growth" in query_lower:
        return "area"
    # Default to bar chart
    return "bar"


def _detect_data_type(query_lower: str) -> str:
    """Detect what type of data user is asking about"""
    if "invoice" in query_lower or "payment" in query_lower or "due" in query_lower:
        return "invoice"
    elif "cash" in query_lower or "flow" in query_lower or "inflow" in query_lower or "outflow" in query_lower:
        return "cashflow"
    elif "expense" in query_lower or "cost" in query_lower:
        return "expense"
    elif "revenue" in query_lower or "sales" in query_lower or "income" in query_lower:
        return "revenue"
    elif "forecast" in query_lower or "prediction" in query_lower:
        return "forecast"
    return "general"


def _generate_bar_chart(data_type: str, dataset: dict, db: Session) -> ChartDataSchema:
    """Generate bar chart data based on data type"""
    
    if data_type == "invoice":
        # Bar chart of invoice status distribution
        status_summary = db.query(
            AppInvoice.status,
            func.count(AppInvoice.invoice_number).label("count"),
            func.sum(AppInvoice.balance_due).label("total_amount")
        ).group_by(AppInvoice.status).all()
        
        data = [
            {
                "status": status or "Unknown",
                "count": count or 0,
                "amount": float(amount or 0)
            }
            for status, count, amount in status_summary
        ]
        
        # Calculate insights
        total_invoices = sum(d["count"] for d in data)
        total_due = sum(d["amount"] for d in data)
        insights = [
            f"Total of {total_invoices} invoices with ${total_due:,.0f} in outstanding balance",
            f"Paid invoices represent {((next((d['amount'] for d in data if 'Paid' in d['status']), 0) / total_due * 100) if total_due > 0 else 0):.1f}% of total invoice value",
            "Focus on overdue invoices to improve cash flow position"
        ]
        
        return ChartDataSchema(
            type="bar",
            data=data,
            xKey="status",
            yKey=["count", "amount"],
            title="Invoice Status Distribution",
            subtitle="Summary of invoices by status and amount",
            colors=["#3b82f6", "#10b981"],
            insights=insights
        )
    
    elif data_type == "cashflow":
        # Bar chart of cash inflows vs outflows by week
        data = [
            {
                "week": "Week 1",
                "inflows": 25000,
                "outflows": 18000
            },
            {
                "week": "Week 2",
                "inflows": 32000,
                "outflows": 21000
            },
            {
                "week": "Week 3",
                "inflows": 28000,
                "outflows": 19000
            },
            {
                "week": "Week 4",
                "inflows": 35000,
                "outflows": 22000
            }
        ]
        
        avg_net = sum((d["inflows"] - d["outflows"]) for d in data) / len(data)
        max_week = max(data, key=lambda x: x["inflows"] - x["outflows"])
        
        insights = [
            f"Average weekly net cash flow: ${avg_net:,.0f}",
            f"Best performing week: {max_week['week']} with net inflow of ${(max_week['inflows'] - max_week['outflows']):,.0f}",
            "Consistent inflow exceeds outflow, indicating positive cash position"
        ]
        
        return ChartDataSchema(
            type="bar",
            data=data,
            xKey="week",
            yKey=["inflows", "outflows"],
            title="Cash Flow by Week",
            subtitle="Inflows vs Outflows comparison",
            colors=["#10b981", "#ef4444"],
            insights=insights
        )
    
    else:
        # Default bar chart
        data = [
            {"category": "Category A", "value": 1000},
            {"category": "Category B", "value": 1500},
            {"category": "Category C", "value": 1200}
        ]
        
        return ChartDataSchema(
            type="bar",
            data=data,
            xKey="category",
            yKey="value",
            title="Data Breakdown",
            subtitle="Distribution across categories"
        )


def _generate_line_chart(data_type: str, dataset: dict, db: Session) -> ChartDataSchema:
    """Generate line chart data based on data type"""
    
    if data_type == "forecast" or data_type == "revenue":
        # Revenue trend with forecast
        data = [
            {"month": "January", "actual": 45000, "forecast": 44000},
            {"month": "February", "actual": 52000, "forecast": 51000},
            {"month": "March", "actual": 61000, "forecast": 59000},
            {"month": "April", "actual": 58000, "forecast": 62000},
            {"month": "May", "actual": 67000, "forecast": 68000},
            {"month": "June", "actual": 75000, "forecast": 72000}
        ]
        
        avg_actual = sum(d["actual"] for d in data) / len(data)
        avg_forecast = sum(d["forecast"] for d in data) / len(data)
        trend = "upward" if data[-1]["actual"] > data[0]["actual"] else "downward"
        accuracy = 100 - (abs(sum(d["actual"] - d["forecast"] for d in data) / len(data)) / avg_actual * 100)
        
        insights = [
            f"Average monthly revenue: ${avg_actual:,.0f} (actual) vs ${avg_forecast:,.0f} (forecast)",
            f"Overall trend is {trend}: from ${data[0]['actual']:,.0f} to ${data[-1]['actual']:,.0f}",
            f"Forecast accuracy: {max(0, accuracy):.1f}% - Consider reviewing forecast model"
        ]
        
        return ChartDataSchema(
            type="line",
            data=data,
            xKey="month",
            yKey=["actual", "forecast"],
            title="Revenue Trend with Forecast",
            subtitle="Historical vs Projected Revenue Performance",
            colors=["#3b82f6", "#f59e0b"],
            insights=insights
        )
    
    elif data_type == "cashflow":
        # Cash position trend
        data = [
            {"week": "Week 1", "position": 250000},
            {"week": "Week 2", "position": 268000},
            {"week": "Week 3", "position": 275000},
            {"week": "Week 4", "position": 288000},
            {"week": "Week 5", "position": 295000},
            {"week": "Week 6", "position": 310000},
            {"week": "Week 7", "position": 318000},
            {"week": "Week 8", "position": 325000}
        ]
        
        growth = ((data[-1]["position"] - data[0]["position"]) / data[0]["position"] * 100)
        avg_growth = growth / (len(data) - 1)
        
        insights = [
            f"Cash position growth: ${data[-1]['position'] - data[0]['position']:,.0f} ({growth:.1f}%)",
            f"Average weekly growth: ${avg_growth/100 * data[0]['position']:,.0f}",
            "Consistent growth trend indicates strong financial health"
        ]
        
        return ChartDataSchema(
            type="line",
            data=data,
            xKey="week",
            yKey="position",
            title="Cash Position Trend",
            subtitle="Weekly Cash Position Growth",
            colors=["#10b981"],
            insights=insights
        )
    
    else:
        # Default trend chart
        data = [
            {"period": "Period 1", "value": 100},
            {"period": "Period 2", "value": 120},
            {"period": "Period 3", "value": 115},
            {"period": "Period 4", "value": 140}
        ]
        
        return ChartDataSchema(
            type="line",
            data=data,
            xKey="period",
            yKey="value",
            title="Trend Analysis",
            subtitle="Value changes over time"
        )


def _generate_pie_chart(data_type: str, dataset: dict, db: Session) -> ChartDataSchema:
    """Generate pie chart data based on data type"""
    
    if data_type == "invoice":
        # Invoice status distribution
        status_summary = db.query(
            AppInvoice.status,
            func.sum(AppInvoice.balance_due).label("total")
        ).group_by(AppInvoice.status).all()
        
        data = [
            {
                "name": status or "Unknown",
                "value": float(total or 0)
            }
            for status, total in status_summary
        ]
        
        total_value = sum(d["value"] for d in data)
        largest = max(data, key=lambda x: x["value"]) if data else None
        
        insights = [
            f"Total invoice value: ${total_value:,.0f}",
            f"Largest segment: {largest['name']} at ${largest['value']:,.0f} ({(largest['value']/total_value*100):.1f}%)" if largest else "",
            "Review large outstanding segments for collection priority"
        ]
        
        return ChartDataSchema(
            type="pie",
            data=data,
            yKey="value",
            title="Revenue Distribution by Invoice Status",
            subtitle="Invoice value breakdown",
            colors=["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"],
            insights=[i for i in insights if i]
        )
    
    elif data_type == "expense":
        # Expense distribution by category
        data = [
            {"name": "Salaries", "value": 150000},
            {"name": "Operations", "value": 75000},
            {"name": "Marketing", "value": 45000},
            {"name": "Technology", "value": 30000},
            {"name": "Other", "value": 20000}
        ]
        
        total = sum(d["value"] for d in data)
        top_expense = max(data, key=lambda x: x["value"])
        
        insights = [
            f"Total expenses: ${total:,.0f}",
            f"Largest expense: {top_expense['name']} at {(top_expense['value']/total*100):.1f}% of total",
            "Monitor high-value categories for cost optimization opportunities"
        ]
        
        return ChartDataSchema(
            type="pie",
            data=data,
            yKey="value",
            title="Expense Distribution by Category",
            subtitle="Spending breakdown by category",
            colors=["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"],
            insights=insights
        )
    
    else:
        # Default pie chart
        data = [
            {"name": "Component A", "value": 45},
            {"name": "Component B", "value": 30},
            {"name": "Component C", "value": 25}
        ]
        
        return ChartDataSchema(
            type="pie",
            data=data,
            yKey="value",
            title="Distribution Breakdown",
            subtitle="Proportion of components"
        )


def _generate_area_chart(data_type: str, dataset: dict, db: Session) -> ChartDataSchema:
    """Generate area chart data based on data type"""
    
    if data_type == "revenue":
        # Cumulative revenue growth
        data = [
            {"month": "January", "revenue": 45000, "costs": 30000},
            {"month": "February", "revenue": 97000, "costs": 61000},
            {"month": "March", "revenue": 158000, "costs": 91000},
            {"month": "April", "revenue": 216000, "costs": 124000},
            {"month": "May", "revenue": 283000, "costs": 156000},
            {"month": "June", "revenue": 358000, "costs": 188000}
        ]
        
        final_revenue = data[-1]["revenue"]
        final_costs = data[-1]["costs"]
        profit_margin = ((final_revenue - final_costs) / final_revenue * 100)
        
        insights = [
            f"Cumulative revenue: ${final_revenue:,.0f} (6-month total)",
            f"Cumulative costs: ${final_costs:,.0f} (6-month total)",
            f"Overall profit margin: {profit_margin:.1f}% - Excellent performance"
        ]
        
        return ChartDataSchema(
            type="area",
            data=data,
            xKey="month",
            yKey=["revenue", "costs"],
            title="Cumulative Revenue vs Costs",
            subtitle="Year-to-date cumulative performance",
            colors=["#10b981", "#ef4444"],
            insights=insights
        )
    
    elif data_type == "cashflow":
        # Cash position accumulation
        data = [
            {"month": "January", "cash": 250000},
            {"month": "February", "cash": 268000},
            {"month": "March", "cash": 275000},
            {"month": "April", "cash": 288000},
            {"month": "May", "cash": 295000},
            {"month": "June", "cash": 310000}
        ]
        
        growth = ((data[-1]["cash"] - data[0]["cash"]) / data[0]["cash"] * 100)
        
        insights = [
            f"Total cash growth: ${data[-1]['cash'] - data[0]['cash']:,.0f} ({growth:.1f}%)",
            f"Starting cash position: ${data[0]['cash']:,.0f}",
            f"Ending cash position: ${data[-1]['cash']:,.0f} - Strong liquidity position"
        ]
        
        return ChartDataSchema(
            type="area",
            data=data,
            xKey="month",
            yKey="cash",
            title="Cash Position Growth",
            subtitle="Monthly accumulated cash position",
            colors=["#3b82f6"],
            insights=insights
        )
    
    else:
        # Default area chart
        data = [
            {"period": "Period 1", "value": 100},
            {"period": "Period 2", "value": 220},
            {"period": "Period 3", "value": 335},
            {"period": "Period 4", "value": 475}
        ]
        
        return ChartDataSchema(
            type="area",
            data=data,
            xKey="period",
            yKey="value",
            title="Cumulative Growth",
            subtitle="Accumulated value over time"
        )


def _enhance_with_professional_formatting(response: str, chart_data: ChartDataSchema) -> str:
    """
    Enhance the response with professional formatting and structure.
    """
    # Create a structured response with professional tone
    enhanced_response = f"""📊 **{chart_data.title}**

{response}

**Chart Details:**
• Chart Type: {chart_data.type.capitalize()} Chart
• Data Points: {len(chart_data.data)} entries
• Subtitle: {chart_data.subtitle or 'N/A'}

**Recommendation:**
Review the visualization below for detailed insights and trends. The chart provides a clear view of your data patterns and helps identify key opportunities for improvement."""

    return enhanced_response
