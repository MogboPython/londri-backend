import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.transactions.schemas import (
    PaginationMeta,
    TransactionListResponse,
    TransactionResponse,
)
from app.core.session import get_db_session
from app.models.transaction import TransactionStatus
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.payment import PaymentService, get_payment_service
from app.services.transaction import TransactionService
from app.util.periods import Period

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def get_transaction_service(
    session: AsyncSession = Depends(get_db_session),
    nomba_payment: PaymentService = Depends(get_payment_service),
) -> TransactionService:
    return TransactionService(
        BusinessRepository(session),
        TransactionRepository(session),
        nomba_payment,
    )


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="Get all transactions for the owner's business, with pagination and available balance",
)
async def get_transactions(
    transaction_status: TransactionStatus | None = Query(default=None, alias="status"),
    reference_id: str | None = Query(default=None),
    period: Period = Query(default=Period.this_month),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=20, gt=0, le=100),
    offset: int = Query(default=0, ge=0),
    owner: User = Depends(require_owner),
    svc: TransactionService = Depends(get_transaction_service),
):
    result = await svc.get_transactions(
        owner,
        transaction_status=transaction_status,
        reference_id=reference_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return TransactionListResponse(
        transactions=[TransactionResponse(**t) for t in result["transactions"]],
        pagination=PaginationMeta(total=result["total"], limit=limit, offset=offset),
        available_balance=result["available_balance"],
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a transaction by ID (owner only)",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    owner: User = Depends(require_owner),
    svc: TransactionService = Depends(get_transaction_service),
):
    result = await svc.get_transaction_by_id(owner, transaction_id)
    return TransactionResponse(**result)
