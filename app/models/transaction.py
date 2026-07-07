import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLEnum
from enum import Enum

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TransactionStatus(str, Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    refunded = "refunded"


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "transactions"

    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="SET NULL"),
        nullable=True,
    )

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Human-Readable UI Reference (e.g., PAY-20260618-JKL012)
    reference_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    merchant_tx_ref: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="NGN")

    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(TransactionStatus, name="transaction_status_enum", create_type=True),
        nullable=False,
        default=TransactionStatus.pending,
        server_default=TransactionStatus.pending.value,
    )

    payment_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order | None"] = relationship("Order", back_populates="transactions")
    subscription: Mapped["CustomerSubscription | None"] = relationship(  # noqa: F821
        "CustomerSubscription", back_populates="transactions"
    )

    __table_args__ = (
        Index("ix_transactions_business_id", "business_id"),
        Index("ix_transactions_order_id", "order_id"),
        Index("ix_transactions_subscription_id", "subscription_id"),
        Index("ix_transactions_merchant_tx_ref", "merchant_tx_ref"),
        Index("ix_transactions_business_date", "business_id", "created_at"),
    )



# class PayoutStatus(str):
#     pending = "pending"
#     processing = "processing"
#     completed = "completed"
#     failed = "failed"
#
#
# class Payout(Base, UUIDPrimaryKeyMixin, TimestampMixin):
#     """Records a payout transfer from the platform's Nomba wallet to a laundry's bank account."""
#
#     __tablename__ = "payouts"
#
#     business_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("businesses.id", ondelete="RESTRICT"),
#         nullable=False,
#     )
#     amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
#     commission_deducted: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
#     currency: Mapped[str] = mapped_column(String(5), nullable=False, default="NGN")
#     status: Mapped[str] = mapped_column(String(20), nullable=False, default=PayoutStatus.pending)
#
#     nomba_transfer_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
#
#     # Billing period the payout covers
#     period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
#     period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
#
#     initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
#     completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
#
#     failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
#
#     # ------------------------------------------------------------------ #
#     # Relationships
#     # ------------------------------------------------------------------ #
#     business: Mapped["Business"] = relationship("Business", back_populates="payouts")  # noqa: F821
#
#     __table_args__ = (
#         Index("ix_payouts_business_id", "business_id"),
#         Index("ix_payouts_status", "status"),
#         Index("ix_payouts_period_start", "period_start"),
#         Index("ix_payouts_nomba_transfer_ref", "nomba_transfer_ref"),
#     )
#
#     def __repr__(self) -> str:
#         return f"<Payout id={self.id} business_id={self.business_id} amount={self.amount}>"

