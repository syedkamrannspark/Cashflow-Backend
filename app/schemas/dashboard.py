from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union

class ChartDataSchema(BaseModel):
    """Schema for visualization chart data"""
    type: str  # 'line', 'bar', 'pie', 'area'
    data: List[Dict[str, Any]]
    xKey: Optional[str] = None
    yKey: Optional[Union[str, List[str]]] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    colors: Optional[List[str]] = None
    insights: Optional[List[str]] = None

class QueryResponse(BaseModel):
    """Response for user queries with optional chart data"""
    response: str
    chartData: Optional[ChartDataSchema] = None

class DetailedBreakdown(BaseModel):
    key: str
    value: float
    label: str

class StatBreakdown(BaseModel):
    summary: str
    breakdown: List[DetailedBreakdown]
    trend: str
    insights: str

class CashPosition(BaseModel):
    current: float
    forecast30Day: float
    atRiskInvoices: float
    cashRunway: int
    currentChangePercent: float
    forecastChangePercent: float
    overdueInvoicesCount: int
    # Detailed breakdowns for popovers
    currentBreakdown: Optional[StatBreakdown] = None
    forecastBreakdown: Optional[StatBreakdown] = None
    atRiskBreakdown: Optional[StatBreakdown] = None
    runwayBreakdown: Optional[StatBreakdown] = None

class ChartDataPoint(BaseModel):
    date: str
    actual: float
    forecasted: float

class CashFlowDataPoint(BaseModel):
    week: str
    date: str
    inflows: float
    outflows: float

class ShortfallPeriod(BaseModel):
    week: str
    shortfall: float
    priority: str  # 'High', 'Medium', 'Low'
    closingBalance: float
    projectedInflows: float
    projectedOutflows: float
    netCashFlow: float
    gap: float
    keyDrivers: List[str]

class ShortfallResponse(BaseModel):
    periods: List[ShortfallPeriod]
    totalShortfall: float
    hasShortfalls: bool

class Invoice(BaseModel):
    id: str
    customer: str
    amount: float
    dueDate: str
    status: str
    riskScore: float
    aiPrediction: str

class InvoiceStats(BaseModel):
    totalReceivables: float
    totalAtRiskAmount: float
    collectionRate: float
    activeInvoiceCount: int
    atRiskInvoiceCount: int

class InvoiceResponse(BaseModel):
    items: List[Invoice]
    total: int
    page: int
    limit: int
    stats: Optional[InvoiceStats] = None
