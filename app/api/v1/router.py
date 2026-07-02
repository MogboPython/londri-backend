from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.business.router import router as business_router
from app.api.v1.compliance.router import router as compliance_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(business_router)
api_v1_router.include_router(compliance_router)
