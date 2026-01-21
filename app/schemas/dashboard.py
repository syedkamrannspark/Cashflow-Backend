from pydantic import BaseModel
from typing import List, Optional

class CashPosition(BaseModel):
    current: float
    forecast30Day: float
    atRiskInvoices: float
    cashRunway: int
    currentChangePercent: float
    forecastChangePercent: float
    overdueInvoicesCount: int

class ChartDataPoint(BaseModel):
    date: str
    actual: float
    forecasted: float

class CashFlowDataPoint(BaseModel):
    week: str
    inflows: float
    outflows: float

class Invoice(BaseModel):
    id: str
    customer: str
    amount: float
    dueDate: str
    status: str
    riskScore: float
    aiPrediction: str

class InvoiceResponse(BaseModel):
    items: List[Invoice]
    total: int
    page: int
    limit: int
