import os
import time
from sqlalchemy import text
from app.core.database import SessionLocal, engine

MAX_RETRIES = 5

def apply_indexes():
    """
    Applies indexes to the database using raw SQL.
    Since we don't have Alembic set up, we apply them manually.
    Idempotent: checks if index exists before creating.
    """
    db = SessionLocal()
    
    # Format: (table_name, index_name, column_name)
    indexes_to_create = [
        ("payment_history", "ix_payment_history_payment_date", "payment_date"),
        ("payment_history", "ix_payment_history_payment_status", "payment_status"),
        ("invoices", "ix_invoices_status", "status"),
        ("invoices", "ix_invoices_days_past_due", "days_past_due"),
        ("bank_transactions", "ix_bank_transactions_date", "date")
    ]
    
    print("Applying database indexes...")
    try:
        with engine.connect() as conn:
            for table, idx_name, col in indexes_to_create:
                # Check if index exists
                check_sql = text(f"SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}'")
                exists = conn.execute(check_sql).fetchone()
                
                if not exists:
                    print(f"Creating index {idx_name} on {table}({col})...")
                    # Create index
                    create_sql = text(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} ON {table} ({col})")
                    # Note: CONCURRENTLY cannot run inside a transaction block, 
                    # but simple CREATE INDEX is fine for this scale. We'll omit CONCURRENTLY for simplicity with sqlalchemy transaction management
                    create_sql = text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({col})")
                    conn.execute(create_sql)
                    conn.commit()
                else:
                    print(f"Index {idx_name} already exists.")
                    
        print("All indexes applied successfully.")
        
    except Exception as e:
        print(f"Error applying indexes: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    apply_indexes()
