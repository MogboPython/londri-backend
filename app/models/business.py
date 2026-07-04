import uuid

from geoalchemy2 import Geography
from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from .compliance import VerificationStatus

class Business(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "businesses"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cac_registration_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_premises_photos: Mapped[str | None] = mapped_column(Text, nullable=True) #comma separated image urls

    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )

    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_discoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    owner: Mapped["User"] = relationship("User", back_populates="business")  # noqa: F821
    kyb_verifications: Mapped[list["KybVerification"]] = relationship(
        "KybVerification", back_populates="business", cascade="all, delete-orphan"
    )
    subaccounts: Mapped[list["BusinessSubaccount"]] = relationship(
        "BusinessSubaccount", back_populates="business", cascade="all, delete-orphan"
    )
    current_kyb_status: Mapped["VerificationStatus"] = mapped_column(
        ENUM(
            VerificationStatus,
            name="verification_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=VerificationStatus.pending,
        server_default="pending",
    )
    price_list_items: Mapped[list["PriceListItem"]] = relationship(
        "PriceListItem", back_populates="business", cascade="all, delete-orphan"
    )
    subscription_plans: Mapped[list["SubscriptionPlan"]] = relationship(
        "SubscriptionPlan", back_populates="business", cascade="all, delete-orphan"
    )
    categories: Mapped[list["Category"]] = relationship(
        "Category", back_populates="business", cascade="all, delete-orphan"
    )
    # orders: Mapped[list["Order"]] = relationship(  # noqa: F821
    #     "Order", back_populates="business"
    # )
    # payouts: Mapped[list["Payout"]] = relationship(  # noqa: F821
    #     "Payout", back_populates="business"
    # )

    __table_args__ = (
        Index("ix_businesses_owner_user_id", "owner_user_id", unique=True),
        Index("ix_business_name", "name"),
        Index("ix_businesses_city", "city"),
        Index("ix_businesses_state", "state"),
    )

    def __repr__(self) -> str:
        return f"<Business id={self.id} name={self.name} kyb_status={self.current_kyb_status}>"
