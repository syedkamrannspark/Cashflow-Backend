from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String

from app.core.database import Base


class CSVDocument(Base):
    __tablename__ = "csv_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True, nullable=False)
    preview = Column(JSON, nullable=True)
    full_data = Column(JSON, nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    column_count = Column(Integer, nullable=False, default=0)
    is_described = Column(Boolean, default=False)
    upload_date = Column(DateTime, default=datetime.utcnow)


class CSVDocumentCreate(BaseModel):
    filename: str
    preview_data: List[Dict[str, Any]]
    full_data: List[Dict[str, Any]]
    row_count: int
    column_count: int


class CSVDocumentResponse(BaseModel):
    id: int
    filename: str
    preview: List[Dict[str, Any]]
    row_count: int
    column_count: int
    is_described: bool
    upload_date: datetime

    class Config:
        orm_mode = True


class CSVDocumentDetail(CSVDocumentResponse):
    full_data: Optional[List[Dict[str, Any]]] = None

    class Config:
        orm_mode = True


class CSVDocumentList(CSVDocumentResponse):
    class Config:
        orm_mode = True


class UploadResponse(BaseModel):
    success: bool
    data: List[CSVDocumentResponse]
    message: str


class ErrorResponse(BaseModel):
    success: bool
    message: str
