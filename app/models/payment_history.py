from sqlalchemy import Column, Integer, String, Float, Date
from app.core.database import Base

class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String, index=True)
    customer_name = Column(String, index=True)
    account_type = Column(String)
    invoice_number = Column(String, index=True) # REMOVED unique=True
    billing_date = Column(Date)
    due_date = Column(Date)
    payment_date = Column(Date, nullable=True, index=True)
    invoice_amount = Column(Float)
    late_fee = Column(Float)
    amount_paid = Column(Float)
    payment_method = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True)
    days_late = Column(Integer)
    payment_status = Column(String, index=True)
    on_time_payment = Column(String)
