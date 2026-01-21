from app.core.database import SessionLocal, engine, Base
from app.services.ingestion_service import ingest_data
import os
# Ensure models are imported so Base knows them
import app.models.payment_history

if __name__ == "__main__":
    print("Creating tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        exit(1)
    
    db = SessionLocal()
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        xlsx_dir = os.path.join(current_dir, "xlsx")
        print(f"Starting ingestion from {xlsx_dir}")
        ingest_data(db, xlsx_dir)
        print("Ingestion complete.")
    except Exception as e:
        print(f"Ingestion failed: {e}")
    finally:
        db.close()
