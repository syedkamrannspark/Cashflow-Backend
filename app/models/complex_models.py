from sqlalchemy import Column, Integer, String, Float, Date, Text
from app.core.database import Base

class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=True, index=True)
    description = Column(String)
    debits = Column(Float, nullable=True)
    credits = Column(Float, nullable=True)
    balance = Column(Float, nullable=True)
    
class ForecastMetric(Base):
    __tablename__ = "forecast_metrics"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True) # "Sales", "Expense", "CustomerPayment"
    metric_name = Column(String)
    value_raw = Column(String)
    period = Column(String, nullable=True)
