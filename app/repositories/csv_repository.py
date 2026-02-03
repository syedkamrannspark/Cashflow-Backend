from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.csv_document import CSVDocument, CSVDocumentCreate, CSVDocumentDetail, CSVDocumentList, CSVDocumentResponse


class CSVRepository:
    @staticmethod
    def _to_response(document: CSVDocument) -> CSVDocumentResponse:
        return CSVDocumentResponse(
            id=document.id,
            filename=document.filename,
            preview=document.preview or [],
            row_count=document.row_count,
            column_count=document.column_count,
            is_described=document.is_described,
            upload_date=document.upload_date,
        )

    @staticmethod
    def _to_detail(document: CSVDocument) -> CSVDocumentDetail:
        return CSVDocumentDetail(
            id=document.id,
            filename=document.filename,
            preview=document.preview or [],
            full_data=document.full_data or [],
            row_count=document.row_count,
            column_count=document.column_count,
            is_described=document.is_described,
            upload_date=document.upload_date,
        )

    @staticmethod
    async def create_document(document_data: CSVDocumentCreate) -> CSVDocumentResponse:
        db: Session = SessionLocal()
        try:
            document = CSVDocument(
                filename=document_data.filename,
                preview=document_data.preview_data,
                full_data=document_data.full_data,
                row_count=document_data.row_count,
                column_count=document_data.column_count,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            return CSVRepository._to_response(document)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    async def get_document_by_id(document_id: int) -> Optional[CSVDocumentDetail]:
        db: Session = SessionLocal()
        try:
            document = db.query(CSVDocument).filter(CSVDocument.id == document_id).first()
            if not document:
                return None
            return CSVRepository._to_detail(document)
        finally:
            db.close()

    @staticmethod
    async def get_document_preview_by_id(document_id: int) -> Optional[CSVDocument]:
        db: Session = SessionLocal()
        try:
            return db.query(CSVDocument).filter(CSVDocument.id == document_id).first()
        finally:
            db.close()

    @staticmethod
    async def list_documents(limit: int = 100, offset: int = 0) -> List[CSVDocumentList]:
        db: Session = SessionLocal()
        try:
            documents = (
                db.query(CSVDocument)
                .order_by(CSVDocument.upload_date.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                CSVDocumentList(
                    id=document.id,
                    filename=document.filename,
                    preview=document.preview or [],
                    row_count=document.row_count,
                    column_count=document.column_count,
                    is_described=document.is_described,
                    upload_date=document.upload_date,
                )
                for document in documents
            ]
        finally:
            db.close()

    @staticmethod
    async def list_documents_with_full_data() -> List[CSVDocumentDetail]:
        db: Session = SessionLocal()
        try:
            documents = db.query(CSVDocument).order_by(CSVDocument.upload_date.desc()).all()
            return [CSVRepository._to_detail(document) for document in documents]
        finally:
            db.close()

    @staticmethod
    async def update_document_description_status(document_id: int, is_described: bool) -> bool:
        db: Session = SessionLocal()
        try:
            document = db.query(CSVDocument).filter(CSVDocument.id == document_id).first()
            if not document:
                return False
            document.is_described = is_described
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    async def delete_document(document_id: int) -> bool:
        db: Session = SessionLocal()
        try:
            document = db.query(CSVDocument).filter(CSVDocument.id == document_id).first()
            if not document:
                return False
            db.delete(document)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    async def document_exists_by_filename(filename: str) -> bool:
        db: Session = SessionLocal()
        try:
            return db.query(CSVDocument).filter(CSVDocument.filename == filename).first() is not None
        finally:
            db.close()
