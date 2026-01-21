from fastapi import APIRouter
from app.api.v1.endpoints import dashboard, invoices

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
