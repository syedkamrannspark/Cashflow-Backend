from sqlalchemy import Column, Integer, String, Float, Date
from app.core.database import Base

class AppInvoice(Base):
    __tablename__ = "invoices"

    invoice_number = Column(String, primary_key=True, index=True)
    account_number = Column(String, nullable=True)
    customer_name = Column(String)
    due_date = Column(Date)
    invoice_date = Column(Date)
    total_amount = Column(Float)
    amount_paid = Column(Float)
    balance_due = Column(Float)
    status = Column(String, index=True)
    days_past_due = Column(Integer, index=True)
