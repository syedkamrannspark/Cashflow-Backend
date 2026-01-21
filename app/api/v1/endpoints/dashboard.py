from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.database import get_db
from app.models.invoice import AppInvoice
from app.models.payment_history import PaymentHistory
from app.models.complex_models import ForecastMetric
from app.schemas.dashboard import CashPosition, ChartDataPoint, CashFlowDataPoint
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

@router.get("/stats", response_model=CashPosition)
def get_dashboard_stats(db: Session = Depends(get_db)):
    # Simple logic to aggregate data
    
    # 1. At Risk Invoices
    at_risk_query = db.query(AppInvoice).filter(AppInvoice.days_past_due > 0)
    at_risk_amount = at_risk_query.with_entities(func.sum(AppInvoice.balance_due)).scalar() or 0
    at_risk_count = at_risk_query.count()
    
    # 2. Forecast 30 Day (Invoices due in next 30 days)
    today = datetime.date.today()
    next_30 = today + datetime.timedelta(days=30)
    forecast_query = db.query(AppInvoice).filter(
        AppInvoice.due_date >= today,
        AppInvoice.due_date <= next_30
    )
    forecast_amount = forecast_query.with_entities(func.sum(AppInvoice.balance_due)).scalar() or 0
    
    # 3. Current Cash (Placeholder or from Payments)
    # We'll use a hardcoded baseline + some recent collection logic or just a large number
    current_cash = 10745698.0  # From Bank Statement
    
    return CashPosition(
        current=current_cash,
        forecast30Day=forecast_amount,
        atRiskInvoices=at_risk_amount,
        cashRunway=45, # Placeholder logic
        currentChangePercent=5.2,
        forecastChangePercent=-2.1,
        overdueInvoicesCount=at_risk_count
    )

@router.get("/forecast", response_model=List[ChartDataPoint])
def get_cash_forecast(db: Session = Depends(get_db)):
    # 1. Get Forecast data from Metrics
    avg_rev_metric = db.query(ForecastMetric).filter(
        ForecastMetric.category == "Sales", 
        ForecastMetric.metric_name.ilike("%Average Monthly Revenue%")
    ).first()
    
    avg_rev = parse_currency(avg_rev_metric.value_raw) if avg_rev_metric else 18000000.0 # Fallback
    weekly_forecast = avg_rev / 4.0

    # 2. Get Actual History (Last 4 weeks from PaymentHistory)
    # Determine anchor date (latest payment date)
    max_date = db.query(func.max(PaymentHistory.payment_date)).scalar()
    end_date = max_date if max_date else datetime.date.today()
    start_date = end_date - datetime.timedelta(days=28) # 4 weeks
    
    payments = db.query(PaymentHistory).filter(
        PaymentHistory.payment_date >= start_date,
        PaymentHistory.payment_date <= end_date
    ).all()
    
    # Aggregate by week
    weekly_actuals = {}
    for p in payments:
        if not p.payment_date: continue
        # Simple week bucketing: (date - start_date).days // 7
        week_idx = (p.payment_date - start_date).days // 7
        if week_idx < 0: week_idx = 0
        if week_idx > 3: week_idx = 3
        
        key = f"Week {week_idx + 1}"
        weekly_actuals[key] = weekly_actuals.get(key, 0) + (p.amount_paid or 0)

    data_points = []
    for i in range(1, 5):
        key = f"Week {i}"
        actual = weekly_actuals.get(key, 0)
        # If actual is 0 (no data), maybe use forecast or 0? Use 0.
        
        data_points.append(ChartDataPoint(
            date=key,
            actual=actual,
            forecasted=weekly_forecast
        ))
        
    return data_points

from app.services.llm_service import get_insights

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
def get_cash_flow(db: Session = Depends(get_db)):
    # Inflows: Payments Received (PaymentHistory)
    # Outflows: Expense Forecast (proxy) / 4
    
    avg_exp_metric = db.query(ForecastMetric).filter(
        ForecastMetric.category == "Expense",
        ForecastMetric.metric_name.ilike("%Average Monthly Expenses%")
    ).first()
    avg_exp = parse_currency(avg_exp_metric.value_raw) if avg_exp_metric else 5000000.0
    weekly_outflow = avg_exp / 4.0
    
    # Inflows (Last 4 weeks)
    max_date = db.query(func.max(PaymentHistory.payment_date)).scalar()
    end_date = max_date if max_date else datetime.date.today()
    start_date = end_date - datetime.timedelta(days=28)
    
    payments = db.query(PaymentHistory).filter(
        PaymentHistory.payment_date >= start_date,
        PaymentHistory.payment_date <= end_date
    ).all()
    
    weekly_inflows = {}
    for p in payments:
        if not p.payment_date: continue
        week_idx = (p.payment_date - start_date).days // 7
        if week_idx > 3: week_idx = 3
        
        key = f"Week {week_idx + 1}"
        weekly_inflows[key] = weekly_inflows.get(key, 0) + (p.amount_paid or 0)

    result = []
    for i in range(1, 5):
        key = f"Week {i}"
        inflow = weekly_inflows.get(key, 0)
        result.append(CashFlowDataPoint(
            week=key,
            inflows=inflow,
            outflows=weekly_outflow
        ))
        
    return result
