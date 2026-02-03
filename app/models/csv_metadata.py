from datetime import datetime
from typing import List

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class CSVMetadata(Base):
    __tablename__ = "csv_metadata"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("csv_documents.id"), index=True, nullable=False)
    column_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    connection_key = Column(String, nullable=True)
    alias = Column(String, nullable=True)
    description = Column(String, nullable=True)
    is_target = Column(Boolean, default=False)
    is_helper = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CSVMetadataColumnCreate(BaseModel):
    column_name: str
    data_type: str
    connection_key: str = ""
    alias: str = ""
    description: str = ""
    is_target: bool = False
    is_helper: bool = False


class CSVMetadataSaveRequest(BaseModel):
    document_id: int
    columns: List[CSVMetadataColumnCreate]


class CSVMetadataSaveResponse(BaseModel):
    success: bool
    message: str
    saved_count: int
