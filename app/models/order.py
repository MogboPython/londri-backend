import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Boolean, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SQLEnum
from enum import Enum
from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from decimal import Decimal


class OrderStatus(str, Enum):
    requested = "requested"
    confirmed = "confirmed"
    picked_up = "picked_up"
    in_progress = "in_progress"
    ready_for_pickup = "ready_for_pickup"
    out_for_delivery = "out_for_delivery"
    completed = "completed"
    cancelled = "cancelled"


class PaymentStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    refunded = "refunded"


class Channel(str, Enum):
    online_booking = "online_booking"
    walk_in = "walk_in"
    subscription_fulfillment = "subscription_fulfillment"


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 1. Human-Readable Display ID (e.g., LDR-20260618-0003)
    reference_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    channel: Mapped[Channel] = mapped_column(
        SQLEnum(Channel, name="channel_enum", create_type=True),
        nullable=False,
        default=Channel.online_booking,
        server_default=Channel.online_booking.value,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OrderStatus.requested.value
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, name="payment_status_enum", create_type=True),
        nullable=False,
        default=PaymentStatus.pending,
        server_default=PaymentStatus.pending.value,
    )

    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)

    to_be_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    scheduled_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    status_events: Mapped[list["OrderStatusEvent"]] = relationship(
        "OrderStatusEvent", back_populates="order", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="order"
    )

    __table_args__ = (
        Index("ix_orders_business_status", "business_id", "status"),
        Index("ix_orders_business_channel", "business_id", "channel"),
        Index("ix_orders_business_payment", "business_id", "payment_status"),
        Index("ix_orders_business_date", "business_id", "created_at"),
        Index("ix_orders_business_whatsapp", "business_id", "customer_whatsapp"),
        Index("ix_orders_business_email", "business_id", "customer_email"),
        Index("ix_orders_reference_id", "reference_id"),
        Index("ix_orders_idempotency_key", "idempotency_key"),
    )


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Line item within an order — references a price list item by ID at time of booking."""

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Nullable FK because the item may be deactivated; we keep name/price as snapshot
    price_list_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_list_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- SNAPSHOT DATA ---
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # NEW: Capture exactly what services were requested (e.g., ['wash', 'iron'])
    service_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        server_default="{}"
    )

    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    price_list_item: Mapped["PriceListItem | None"] = relationship(  # noqa: F821
        "PriceListItem", back_populates="order_items"
    )

    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_price_list_item_id", "price_list_item_id"),
    )


class OrderStatusEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable audit log of every order status transition."""

    __tablename__ = "order_status_events"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # who updated it, null = system
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True) # owner, worker
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    order: Mapped["Order"] = relationship("Order", back_populates="status_events")

    __table_args__ = (
        Index("ix_order_status_events_order_time", "order_id", "timestamp"),
    )
