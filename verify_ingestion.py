
from app.core.database import SessionLocal
from app.models.payment_history import PaymentHistory
from app.models.invoice import AppInvoice
from app.models.complex_models import BankTransaction, ForecastMetric

db = SessionLocal()
print(f"PaymentHistory: {db.query(PaymentHistory).count()}")
print(f"AppInvoice: {db.query(AppInvoice).count()}")
print(f"BankTransaction: {db.query(BankTransaction).count()}")
print(f"ForecastMetric: {db.query(ForecastMetric).count()}")
db.close()
