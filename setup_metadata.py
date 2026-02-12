#!/usr/bin/env python3
"""
Setup metadata for the electricity payments CSV document
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import Settings
from app.models.csv_metadata import CSVMetadata
import datetime

# Get database URL
settings = Settings()
database_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Define metadata for the electricity payments CSV
metadata_columns = [
    {
        "document_id": 20,
        "column_name": "Account Number",
        "data_type": "string",
        "connection_key": "",
        "alias": "Account",
        "description": "Customer account identifier",
        "is_target": False,
        "is_helper": False
    },
    {
        "document_id": 20,
        "column_name": "Customer Name",
        "data_type": "string",
        "connection_key": "",
        "alias": "Customer",
        "description": "Name of the customer",
        "is_target": False,
        "is_helper": False
    },
    {
        "document_id": 20,
        "column_name": "Billing Date",
        "data_type": "date",
        "connection_key": "",
        "alias": "Date",
        "description": "Date when invoice was issued",
        "is_target": True,
        "is_helper": False
    },
    {
        "document_id": 20,
        "column_name": "Due Date",
        "data_type": "date",
        "connection_key": "",
        "alias": "Due Date",
        "description": "Payment due date",
        "is_target": False,
        "is_helper": True
    },
    {
        "document_id": 20,
        "column_name": "Payment Date",
        "data_type": "date",
        "connection_key": "",
        "alias": "Payment Date",
        "description": "Actual date payment was made",
        "is_target": True,
        "is_helper": False
    },
    {
        "document_id": 20,
        "column_name": "Invoice Amount",
        "data_type": "numeric",
        "connection_key": "",
        "alias": "Amount Due",
        "description": "Total invoice amount - this is a cash outflow when billed",
        "is_target": True,
        "is_helper": False
    },
    {
        "document_id": 20,
        "column_name": "Amount Paid",
        "data_type": "numeric",
        "connection_key": "",
        "alias": "Amount Paid",
        "description": "Amount paid by customer - this is a cash inflow when received",
        "is_target": True,
        "is_helper": False
    },
    {
        "document_id": 20,
        "column_name": "Payment Status",
        "data_type": "string",
        "connection_key": "",
        "alias": "Status",
        "description": "Payment completion status: Completed, Failed, Pending",
        "is_target": False,
        "is_helper": True
    }
]

# Insert metadata
count = 0
for col in metadata_columns:
    existing = session.query(CSVMetadata).filter(
        CSVMetadata.document_id == col["document_id"],
        CSVMetadata.column_name == col["column_name"]
    ).first()
    
    if not existing:
        metadata = CSVMetadata(
            document_id=col["document_id"],
            column_name=col["column_name"],
            data_type=col["data_type"],
            connection_key=col["connection_key"],
            alias=col["alias"],
            description=col["description"],
            is_target=col["is_target"],
            is_helper=col["is_helper"],
            created_at=datetime.datetime.utcnow()
        )
        session.add(metadata)
        count += 1
        print(f"✓ Added metadata for {col['column_name']}")

session.commit()
session.close()
print(f"\n✓ Total metadata created: {count} columns for document 20")
