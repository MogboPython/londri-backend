import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException, status

from app.models.transaction import Transaction, TransactionStatus
from app.repositories.business_repository import BusinessRepository
from app.repositories.transaction_repository import TransactionRepository
from app.util.periods import Period, resolve_period_range

from ..models import User
from .payment import PaymentService


class TransactionService:
    def __init__(
            self,
            business_repo: BusinessRepository,
            txn_repo: TransactionRepository,
            nomba_payment: PaymentService,
    ) -> None:
        self._txn_repo = txn_repo
        self._business_repo = business_repo
        self._nomba_payment = nomba_payment

    async def _resolve_business(self, owner: User) -> uuid.UUID:
        business = await self._business_repo.get_by_owner(owner.id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business registered for this account.",
            )
        return business.id

    @staticmethod
    def _to_dict(txn: Transaction) -> dict[str, Any]:
        return {
            "id": str(txn.id),
            "business_id": str(txn.business_id) if txn.business_id else None,
            "order_id": str(txn.order_id) if txn.order_id else None,
            "reference_id": txn.reference_id,
            "merchant_tx_ref": txn.merchant_tx_ref,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "status": txn.status,
            "payment_channel": txn.payment_channel,
            "paid_at": txn.paid_at,
            "created_at": txn.created_at,
        }

    async def get_transaction_by_id(self, owner: User, transaction_id: uuid.UUID) -> dict[str, Any]:
        business_id = await self._resolve_business(owner)

        txn = await self._txn_repo.get_by_id(transaction_id)
        if not txn or txn.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

        return self._to_dict(txn)

    async def get_transactions(
            self,
            owner: User,
            *,
            transaction_status: TransactionStatus | None = None,
            reference_id: str | None = None,
            period: Period = Period.this_month,
            start_date: date | None = None,
            end_date: date | None = None,
            limit: int = 20,
            offset: int = 0,
    ) -> dict[str, Any]:
        business_id = await self._resolve_business(owner)
        range_start, range_end = resolve_period_range(period, start_date, end_date)

        transactions = await self._txn_repo.search(
            business_id,
            status=transaction_status,
            reference_id=reference_id,
            start_date=range_start,
            end_date=range_end,
            limit=limit,
            offset=offset,
        )
        total = await self._txn_repo.count_search(
            business_id,
            status=transaction_status,
            reference_id=reference_id,
            start_date=range_start,
            end_date=range_end,
        )

        business = await self._business_repo.get_with_subaccount_details(business_id)
        available_balance = self._nomba_payment.get_available_balance(business.subaccounts[0].provider_subaccount_id)

        return {
            "transactions": [self._to_dict(t) for t in transactions],
            "total": total,
            "available_balance": available_balance,
        }
