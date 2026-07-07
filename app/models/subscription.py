import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionStatus(str, Enum):
    inactive = "inactive"
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"

class CustomerSubscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "customer_subscriptions"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )

    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum", create_type=True),
        nullable=False,
        default=SubscriptionStatus.inactive,
        server_default=SubscriptionStatus.inactive.value,
    )

    # Left unset at creation — a subscription is created `inactive` before payment
    # succeeds, and these are only known once the first charge is confirmed.
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_billing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items_used_in_current_period: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="customer_subscriptions")
    customer: Mapped["User"] = relationship("User", back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship(
        "SubscriptionPlan", back_populates="customer_subscriptions"
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="subscription"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="subscription"
    )

    __table_args__ = (
        Index("ix_customer_subs_business_status", "business_id", "status"),
        Index("ix_customer_subs_customer_id", "customer_id"),
        Index("ix_customer_subs_billing_worker", "status", "next_billing_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<CustomerSubscription id={self.id} customer_id={self.customer_id} "
            f"status={self.status}>"
        )
