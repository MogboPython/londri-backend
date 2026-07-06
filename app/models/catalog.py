import uuid
from typing import List

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    business: Mapped["Business"] = relationship(  # noqa: F821
        "Business", back_populates="categories"
    )
    price_list_items: Mapped[List["PriceListItem"]] = relationship(
        "PriceListItem", back_populates="category"
    )

    __table_args__ = (
        Index("ix_categories_business_id", "business_id"),
        Index("ix_categories_business_id_name", "business_id", "name", unique=True),
    )


class PriceListItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "price_list_items"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_types: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        server_default="{}"
    )

    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    turnaround_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    business: Mapped["Business"] = relationship(
        "Business", back_populates="price_list_items"
    )
    category: Mapped["Category"] = relationship(
        "Category", back_populates="price_list_items"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem", back_populates="price_list_item"
    )

    __table_args__ = (
        Index("ix_price_list_items_business_active", "business_id", "is_active"),
        Index("ix_price_list_items_category_id", "category_id"),
        Index(
            "ix_price_list_items_service_types",
            "service_types",
            postgresql_using="gin"
        ),
    )

class SubscriptionPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A recurring plan offered by a laundry business.
    Plans are versioned: editing a plan creates a new record (new version) rather than
    mutating the existing one, preserving active subscribers' terms.
    """

    __tablename__ = "subscription_plans"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Billing cycle enum string (e.g., "monthly", "weekly")
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    item_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_category_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default="{}"
    )

    cancel_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default="at_period_end"
    )  # "immediately" | "at_period_end"

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Groups all versions of this specific plan family together
    plan_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    business: Mapped["Business"] = relationship(  # noqa: F821
        "Business", back_populates="subscription_plans"
    )
    # customer_subscriptions: Mapped[list["CustomerSubscription"]] = relationship(  # noqa: F821
    #     "CustomerSubscription", back_populates="plan"
    # )

    __table_args__ = (
        Index(
            "ix_subscription_plans_query_v2",
            "business_id", "is_active", "plan_group_id", "version"
        ),
        Index(
            "ix_subscription_plans_eligible_categories",
            "eligible_category_ids",
            postgresql_using="gin",
        ),
    )
