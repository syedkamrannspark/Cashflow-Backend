
from app.core.database import engine, Base
from app.models.payment_history import PaymentHistory
from sqlalchemy import text

# Drop table to apply change
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS payment_history CASCADE"))
    conn.commit()
    print("Dropped payment_history")

# Recreate
Base.metadata.create_all(bind=engine)
print("Recreated tables")
