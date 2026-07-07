import uuid
from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint

from .base import Base, IntPrimaryKeyMixin, TimestampMixin


class SubaccountStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"

class BankAccount(Base, IntPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bank_accounts"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_code: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    user: Mapped["User"] = relationship("User", back_populates="bank_accounts")

    __table_args__ = (
        Index("idx_bank_accounts_user", "user_id"),
        UniqueConstraint(
            "user_id",
            "account_number",
            "bank_code",
            name="uq_user_bank_account",
        ),
    )

class BusinessSubaccount(Base, IntPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_subaccounts"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_subaccount_id: Mapped[str] = mapped_column(String(255), nullable=False)
    virtual_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    virtual_account_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SubaccountStatus] = mapped_column(
        SQLEnum(
            SubaccountStatus,
            name="subaccount_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SubaccountStatus.active,
        server_default="active",
    )

    business: Mapped["Business"] = relationship("Business", back_populates="subaccounts")

    __table_args__ = (
        Index("idx_subaccounts_business", "business_id"),
        UniqueConstraint(
            "provider",
            "provider_subaccount_id",
            name="uq_provider_subaccount",
        ),
    )

class TokenizedCard(Base, IntPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tokenized_cards"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_key: Mapped[str] = mapped_column(String(128), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )

    customer: Mapped["User"] = relationship("User", back_populates="tokenized_cards")

    __table_args__ = (
        Index("ix_tokenized_cards_user_active", "user_id", "is_active"),
        Index("ix_tokenized_cards_account_active", "account_id", "is_active"),
        Index("uq_tokenized_cards_token_key", "token_key", unique=True),
        Index("ix_tokenized_cards_email", "customer_email"),
    )
