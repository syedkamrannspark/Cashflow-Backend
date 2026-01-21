from fastapi import APIRouter
from app.api.v1.endpoints import dashboard, invoices, workflows

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
