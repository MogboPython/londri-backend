import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class UserRole(str, Enum):
    owner = "owner"
    customer = "customer"
    staff = "staff"

# XXX: can extend to oauth later
class AuthMethod(str, Enum):
    password = "password"
    otp = "otp"

class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.customer)
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False, default=AuthMethod.otp)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    otp_records: Mapped[list["OtpRecord"]] = relationship(
        "OtpRecord", back_populates="user", cascade="all, delete-orphan"
    )
    business: Mapped["Business | None"] = relationship(  # noqa: F821
        "Business", back_populates="owner", uselist=False
    )
    kyc_verifications: Mapped[list["KycVerification"]] = relationship( # noqa: F821
        "KycVerification", back_populates="user", cascade="all, delete-orphan"
    )
    bank_accounts: Mapped[list["BankAccount"]] = relationship( # noqa: F821
        "BankAccount", back_populates="user", cascade="all, delete-orphan"
    )

    orders: Mapped[list["Order"]] = relationship( # noqa: F821
        "Order", back_populates="customer", uselist=False
    )

    subscriptions: Mapped[list["CustomerSubscription"]] = relationship(  # noqa: F821
        "CustomerSubscription", back_populates="customer"
    )

    tokenized_cards: Mapped[list["TokenizedCard"]] = relationship(
        "TokenizedCard", back_populates="customer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_phone", "phone", unique=True),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"

class OtpRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "otp_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user: Mapped["User"] = relationship("User", back_populates="otp_records")

    __table_args__ = (
        Index("ix_otp_records_user_id", "user_id"),
        Index("ix_otp_records_expires_at", "expires_at"),
        Index("ix_otp_records_purpose", "purpose")
    )

    def __repr__(self) -> str:
        return f"<OtpRecord id={self.id} user_id={self.user_id} purpose={self.purpose}>"
