from typing import Dict, List

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.csv_metadata import CSVMetadata, CSVMetadataColumnCreate


class CSVMetadataRepository:
    @staticmethod
    async def replace_metadata(document_id: int, columns: List[CSVMetadataColumnCreate]) -> int:
        db: Session = SessionLocal()
        try:
            db.query(CSVMetadata).filter(CSVMetadata.document_id == document_id).delete()
            records = [
                CSVMetadata(
                    document_id=document_id,
                    column_name=column.column_name,
                    data_type=column.data_type,
                    connection_key=column.connection_key,
                    alias=column.alias,
                    description=column.description,
                    is_target=column.is_target,
                    is_helper=column.is_helper,
                )
                for column in columns
            ]
            if records:
                db.add_all(records)
            db.commit()
            return len(records)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    async def list_metadata_by_document_ids(document_ids: List[int]) -> Dict[int, List[CSVMetadata]]:
        db: Session = SessionLocal()
        try:
            if not document_ids:
                return {}
            rows = db.query(CSVMetadata).filter(CSVMetadata.document_id.in_(document_ids)).all()
            grouped: Dict[int, List[CSVMetadata]] = {}
            for row in rows:
                grouped.setdefault(row.document_id, []).append(row)
            return grouped
        finally:
            db.close()
    
    @staticmethod
    async def delete_metadata_by_document_id(document_id: int) -> bool:
        """Delete all metadata records for a document."""
        db: Session = SessionLocal()
        try:
            count = db.query(CSVMetadata).filter(CSVMetadata.document_id == document_id).delete()
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()
