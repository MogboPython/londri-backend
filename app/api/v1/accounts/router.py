from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.accounts.schemas import (
    AccountNameResponse,
    BankAccountResponse,
    BankResponse,
    BankAccountRequest,
)
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.accounts_repository import BankAccountRepository
from app.services.payment.service import PaymentService, get_payment_service
from fastapi import HTTPException

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get(
    "/banks",
    response_model=list[BankResponse],
    summary="Get all banks and their codes",
)
async def get_banks(
    _: User = Depends(require_owner),
    payment_svc: PaymentService = Depends(get_payment_service),
):
    banks = await payment_svc.get_bank_codes()
    return [BankResponse(code=b["code"], name=b["name"]) for b in banks]


@router.get(
    "/bank/lookup",
    response_model=AccountNameResponse,
    summary="Look up account name by account number and bank code",
)
async def lookup_account_name(
    account_number: str = Query(..., min_length=10, max_length=10, pattern=r"^\d{10}$"),
    bank_code: str = Query(..., min_length=2, max_length=20),
    _: User = Depends(require_owner),
    payment_svc: PaymentService = Depends(get_payment_service),
):
    account_name = await payment_svc.get_customer_acc_name(account_number, bank_code)
    return AccountNameResponse(
        account_name=account_name,
        account_number=account_number,
        bank_code=bank_code,
    )


@router.post(
    "/bank",
    response_model=BankAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a verified bank account for the authenticated owner",
)
async def save_bank_account(
    body: BankAccountRequest,
    current_user: User = Depends(require_owner),
    payment_svc: PaymentService = Depends(get_payment_service),
    session: AsyncSession = Depends(get_db_session),
):
    repo = BankAccountRepository(session)

    existing = await repo.get_by_user_and_account(
        current_user.id, body.account_number, body.bank_code
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This bank account has already been saved.",
        )

    # Resolve account name from Nomba — validates the account number + bank code pair
    account_name = await payment_svc.get_customer_acc_name(body.account_number, body.bank_code)

    record = await repo.create(
        user_id=current_user.id,
        account_number=body.account_number,
        bank_code=body.bank_code,
        account_name=account_name,
        is_verified=True,
    )

    return BankAccountResponse(
        id=record.id,
        account_number=record.account_number,
        bank_code=record.bank_code,
        account_name=record.account_name,
        is_default=record.is_default,
    )
