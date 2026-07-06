from datetime import datetime

from pydantic import BaseModel

from app.models.transaction import TransactionStatus


class TransactionResponse(BaseModel):
    id: str
    business_id: str | None
    order_id: str | None
    reference_id: str
    merchant_tx_ref: str
    amount: float
    currency: str
    status: TransactionStatus
    payment_channel: str | None
    paid_at: datetime | None
    created_at: datetime


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    pagination: PaginationMeta
    available_balance: float
