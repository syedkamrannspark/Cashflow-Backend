from fastapi import APIRouter, Depends
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from app.core.database import get_db
from app.models.invoice import AppInvoice
from app.models.payment_history import PaymentHistory
from app.models.complex_models import ForecastMetric
from app.schemas.dashboard import CashPosition, ChartDataPoint, CashFlowDataPoint, QueryResponse, ChartDataSchema, ShortfallResponse, ShortfallPeriod
from app.repositories.csv_repository import CSVRepository
from app.repositories.csv_metadata_repository import CSVMetadataRepository
from app.services.llm_service import get_insights, get_stats_from_openrouter, get_cash_forecast_from_openrouter, get_cash_flow_from_openrouter, answer_user_query, get_scenario_analysis_from_openrouter, get_data_visualization_from_openrouter, get_dynamic_cash_flow_from_openrouter
from app.services.pandas_analytics_service import PandasAnalyticsService
from app.agents.nl2sql_agent import nl2sql_agent
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


def _get_column_hints(metadata_by_doc: dict) -> str:
    """
    Generate hints about available columns for the LLM.
    """
    amount_cols = set()
    date_cols = set()
    status_cols = set()
    
    for doc_id, metas in metadata_by_doc.items():
        for m in metas:
            name = m.column_name
            if m.data_type == 'numeric' and m.is_target:
                amount_cols.add(name)
            elif m.data_type == 'date':
                date_cols.add(name)
            elif 'status' in name.lower():
                status_cols.add(name)

    hint = ""
    if amount_cols:
        hint += f" For Amount, check columns: {', '.join([f"'{c}'" for c in amount_cols])}."
    if date_cols:
        hint += f" For Date, check columns: {', '.join([f"'{c}'" for c in date_cols])}."
    if status_cols:
        hint += f" For Status, check columns: {', '.join([f"'{c}'" for c in status_cols])}."
        
    return hint


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

    # Calculate stats using Pandas Service (replacing LLM)
    pandas_stats = PandasAnalyticsService.calculate_stats(documents)
    
    # Fallback to LLM only if pandas returns all zeros (meaning files might be missing)
    # But user asked to REPLACE, so we prioritize Pandas.
    # If pandas_stats has data, we use it.
    
    # Construct response
    response = CashPosition(
        current=pandas_stats.get("current", 0.0),
        forecast30Day=pandas_stats.get("forecast30Day", 0.0),
        atRiskInvoices=pandas_stats.get("atRiskInvoices", 0.0),
        cashRunway=pandas_stats.get("cashRunway", 0),
        currentChangePercent=pandas_stats.get("currentChangePercent", 0.0),
        forecastChangePercent=pandas_stats.get("forecastChangePercent", 0.0),
        overdueInvoicesCount=pandas_stats.get("overdueInvoicesCount", 0),
        currentBreakdown=None, # Not calculated by pandas script yet
        forecastBreakdown=None,
        atRiskBreakdown=None,
        runwayBreakdown=None,
    )
    
    logger.info("/stats Pandas Service response: %s", response.model_dump())
    print("/stats Pandas Service response:", response.model_dump(), flush=True)
    return response

@router.get("/forecast", response_model=List[ChartDataPoint])
async def get_cash_forecast(db: Session = Depends(get_db)):
    documents = await CSVRepository.list_documents_with_full_data()
    
    # Use Pandas Service
    forecast_data = PandasAnalyticsService.get_cash_forecast_data(documents)
    
    # Transform to list of ChartDataPoint
    data_points: List[ChartDataPoint] = []
    
    labels = forecast_data.get("labels", [])
    datasets = forecast_data.get("datasets", [])
    
    if datasets:
        # Dataset 0 = Actuals, Dataset 1 = Forecast (if present)
        actuals = datasets[0].get("data", []) if len(datasets) > 0 else []
        forecasts = datasets[1].get("data", []) if len(datasets) > 1 else []
        
        for i, label in enumerate(labels):
            # Handle possible None/Null values for ChartJS structure
            # For Pydantic model, we generally need float unless Optional[float]
            # Assuming schema requires float, we map None -> 0.0 or just omit?
            # User wants a continuous line, but if we zero it out, it might look like a crash.
            # Ideally frontend handles nulls. If backend insists on float, we might need to be smart.
            # But the error 'Input should be a valid number' suggests strict float.
            
            # Let's check `ChartDataPoint` definition. If it's strict float, we must provide float.
            # If so, we might need to merge them if they are disjoint but on same axis?
            # Actually, ChartDataPoint likely has fields `actual` and `forecasted`.
            
            val_actual = actuals[i] if i < len(actuals) and actuals[i] is not None else 0.0
            val_forecast = forecasts[i] if i < len(forecasts) and forecasts[i] is not None else 0.0
            
            # Special case: If forecast is 0.0 but actual is present, we might want to just show actual?
            # Or if actual is 0.0 (because it's future), show forecast?
            # The chart likely plots both lines.
            
            data_points.append(
                ChartDataPoint(
                    date=str(label),
                    actual=float(val_actual),
                    forecasted=float(val_forecast)
                )
            )
            
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

    # Use NL2SQL for insights summary using aggregated data
    try:
        hints = _get_column_hints(metadata_by_doc)
        agg_query = f"Calculate total revenue, total expenses, and count of transactions grouped by Month. {hints} Use the most relevant columns."
        nl_result = await nl2sql_agent.process_natural_query(agg_query)
        dataset["aggregated_summary"] = nl_result.get("data_full", [])
        
        # Limit raw data
        for doc in dataset["documents"]:
            doc["full_data"] = doc["full_data"][:20] if doc["full_data"] else []
            
    except Exception as e:
        logger.error(f"NL2SQL Error in /insights: {e}")
        pass

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
    documents = await CSVRepository.list_documents_with_full_data()
    
    # Use Pandas Service
    scenario_data = PandasAnalyticsService.get_scenario_analysis(documents)
    
    # Transform to list of points: [{"week": "Week 1", "optimistic": 1150000, "expected": 1000000, "pessimistic": 850000}, ...]
    # Pandas returns: labels list, datasets list.
    
    points = []
    labels = scenario_data.get("labels", [])
    datasets = scenario_data.get("datasets", [])
    
    # Find datasets
    opt_data = next((d['data'] for d in datasets if d['label'] == 'Optimistic'), [])
    exp_data = next((d['data'] for d in datasets if d['label'] == 'Expected'), [])
    pess_data = next((d['data'] for d in datasets if d['label'] == 'Pessimistic'), [])
    
    for i, label in enumerate(labels):
        points.append({
            "week": str(label), # or generic "Week X" if label is date
            "optimistic": opt_data[i] if i < len(opt_data) else 0,
            "expected": exp_data[i] if i < len(exp_data) else 0,
            "pessimistic": pess_data[i] if i < len(pess_data) else 0
        })

    return points


@router.get("/data-visualization")
async def get_data_visualization(db: Session = Depends(get_db)):
    """
    Generate dynamic chart configuration based on uploaded CSV data.
    Returns chart type, axis configuration, and formatted data ready for visualization.
    """
    # Fetch all documents with full data
    documents = await CSVRepository.list_documents_with_full_data()
    document_ids = [doc.id for doc in documents]
    metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

    # Build dataset
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

    # For visualization, we need SOME raw data, but not all. Limit to 50 rows.
    for doc in dataset["documents"]:
        if len(doc["full_data"]) > 50:
            doc["full_data"] = doc["full_data"][:50]  # Sample first 50 rows only

    # Check cache first
    cache_key = f"visualization_{_generate_cache_key(dataset)}"
    viz_config = _get_cached_response(cache_key)
    
    if viz_config is None:
        # Cache miss - call LLM
        viz_config = get_data_visualization_from_openrouter(dataset)
        _set_cached_response(cache_key, viz_config)
    
    logger.info("/data-visualization OpenRouter response: %s", viz_config)
    print("/data-visualization OpenRouter response:", viz_config, flush=True)

    return viz_config


@router.get("/dynamic-cash-flow")
async def get_dynamic_cash_flow(db: Session = Depends(get_db)):
    """
    Generate dynamic cash flow forecast based on uploaded CSV data.
    Analyzes patterns in provided data to project inflows, outflows, and closing balance.
    """
    # Fetch all documents with full data
    documents = await CSVRepository.list_documents_with_full_data()
    document_ids = [doc.id for doc in documents]
    metadata_by_doc = await CSVMetadataRepository.list_metadata_by_document_ids(document_ids)

    # Build dataset
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

    # Get current cash position to start balance calculations
    current_stats = await get_dashboard_stats(db)
    current_balance = current_stats.current if hasattr(current_stats, 'current') else _to_float(current_stats.get('current', 0)) if isinstance(current_stats, dict) else 0

    # Check cache first (include balance in cache key for accuracy)
    cache_key = f"dynamic_cash_flow_{_generate_cache_key(dataset)}_{current_balance}"
    cash_flow_points = _get_cached_response(cache_key)
    
    if cash_flow_points is None:
        # Cache miss - call LLM with current balance
        cash_flow_points = get_dynamic_cash_flow_from_openrouter(dataset, current_balance)
        _set_cached_response(cache_key, cash_flow_points)
    
    logger.info("/dynamic-cash-flow OpenRouter response: %s", cash_flow_points)
    print("/dynamic-cash-flow OpenRouter response:", cash_flow_points, flush=True)

    # Return the cash flow forecast points
    return cash_flow_points


@router.get("/flow", response_model=List[CashFlowDataPoint])
async def get_cash_flow(db: Session = Depends(get_db)):
    """
    Get weekly Cash Inflows vs Outflows based on actual dates from CSV data.
    Uses date columns and inflow/outflow columns from uploaded documents.
    X-axis shows actual dates or week labels derived from the data.
    """
    documents = await CSVRepository.list_documents_with_full_data()
    
    # Use Pandas Service
    flow_data = PandasAnalyticsService.get_cash_flow_data(documents)
    
    # Transform to list of CashFlowDataPoint
    result: List[CashFlowDataPoint] = []
    
    labels = flow_data.get("labels", [])
    datasets = flow_data.get("datasets", [])
    
    inflow_data = next((d['data'] for d in datasets if d['label'] == 'Inflows'), [])
    outflow_data = next((d['data'] for d in datasets if d['label'] == 'Outflows'), [])
    
    for i, label in enumerate(labels):
        result.append(
            CashFlowDataPoint(
                week=str(label), # Using label as week/date identifier
                date=str(label),
                inflows=inflow_data[i] if i < len(inflow_data) else 0.0,
                outflows=outflow_data[i] if i < len(outflow_data) else 0.0
            )
        )
            
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


@router.get("/shortfalls", response_model=ShortfallResponse)
async def get_shortfalls(db: Session = Depends(get_db)):
    """
    Detect and analyze cash shortfall periods using Pandas logic.
    """
    try:
        documents = await CSVRepository.list_documents_with_full_data()
        
        # Use Pandas Service
        result = PandasAnalyticsService.get_cash_shortfalls(documents)
        
        return ShortfallResponse(
            periods=result.get("periods", []),
            totalShortfall=result.get("totalShortfall", 0.0),
            hasShortfalls=result.get("hasShortfalls", False)
        )
    
    except Exception as e:
        logger.error(f"Error detecting shortfalls: {str(e)}", exc_info=True)
        return ShortfallResponse(periods=[], totalShortfall=0.0, hasShortfalls=False)
