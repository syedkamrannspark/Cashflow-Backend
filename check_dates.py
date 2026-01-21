
from app.core.database import SessionLocal
from app.models.payment_history import PaymentHistory
from sqlalchemy import func

db = SessionLocal()
max_date = db.query(func.max(PaymentHistory.payment_date)).scalar()
min_date = db.query(func.min(PaymentHistory.payment_date)).scalar()
print(f"Min Date: {min_date}")
print(f"Max Date: {max_date}")
db.close()
