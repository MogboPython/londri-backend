from fastapi import APIRouter

from app.api.v1.accounts.router import router as accounts_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.business.router import router as business_router
from app.api.v1.catalog.router import router as catalog_router
from app.api.v1.compliance.router import router as compliance_router
from app.api.v1.orders.router import router as orders_router
from app.api.v1.payment.router import router as payment_router
from app.api.v1.subscriptions.router import router as subscriptions_router
from app.api.v1.transactions.router import router as transactions_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(business_router)
api_v1_router.include_router(compliance_router)
api_v1_router.include_router(accounts_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(transactions_router)
api_v1_router.include_router(payment_router)
api_v1_router.include_router(subscriptions_router)
