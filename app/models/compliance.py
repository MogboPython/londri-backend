import uuid
from datetime import datetime
from enum import Enum
from typing import List

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IntPrimaryKeyMixin, TimestampMixin


class VerificationStatus(str, Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    expired = "expired"

# XXX haven't decided whether I should keep KYC and KYB separate
class KycVerification(Base, IntPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "kyc_verifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_number: Mapped[str] = mapped_column(String(255), nullable=False)
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # XXX: Provider used in verifying
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(
            VerificationStatus,
            name="verification_status_enum",
            create_type=True,
        ),
        nullable=False,
        default=VerificationStatus.pending,
        server_default=VerificationStatus.pending.value,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="kyc_verifications")

    __table_args__ = (
        Index("idx_kyc_user", "user_id"),
        Index("idx_kyc_id_type", "id_type"),
    )

class KybVerification(Base, IntPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "kyb_verifications"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )

    # XXX: should be more serious, but this is just a demo
    proof_of_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    cac_registration_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    business_premises_photos: Mapped[List[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}"
    )
    status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(
            VerificationStatus,
            name="verification_status_enum",
            create_type=True,
        ),
        nullable=False,
        default=VerificationStatus.pending,
        server_default=VerificationStatus.pending.value,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="kyb_verifications")

    __table_args__ = (
        Index("idx_kyb_business", "business_id"),
    )