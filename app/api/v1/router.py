from fastapi import APIRouter
from app.api.v1.endpoints import dashboard, invoices, workflows, csv_controller, metadata_controller

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(csv_controller.router, prefix="/documents", tags=["documents"])
api_router.include_router(metadata_controller.router, prefix="/metadata", tags=["metadata"])
