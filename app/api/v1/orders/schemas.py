import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models.order import Channel, OrderStatus, PaymentStatus


class OrderItemRequest(BaseModel):
    price_list_item_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0)


class CreateOrderRequest(BaseModel):
    business_id: uuid.UUID
    items: list[OrderItemRequest] = Field(..., min_length=1)
    channel: Channel = Channel.online_booking
    customer_name: str | None = None
    customer_email: EmailStr
    customer_whatsapp: str | None = None
    to_be_delivered: bool = False
    delivery_address: str | None = None
    notes: str | None = None
    scheduled_pickup_at: datetime | None = None


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus
    note: str | None = None


class OrderItemResponse(BaseModel):
    id: str
    price_list_item_id: str | None = None
    item_name: str
    service_types: list[str]
    unit: str
    quantity: float
    unit_price: float
    line_total: float


class OrderStatusEventResponse(BaseModel):
    id: str
    from_status: str | None
    to_status: str
    actor_id: str | None
    actor_role: str | None
    note: str | None
    timestamp: datetime


class OrderResponse(BaseModel):
    id: str
    business_id: str
    reference_id: str
    channel: Channel
    status: str
    payment_status: PaymentStatus
    customer_name: str | None
    customer_email: str | None
    customer_whatsapp: str | None
    to_be_delivered: bool
    delivery_address: str | None
    notes: str | None
    amount: float | None
    scheduled_pickup_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse] = Field(default_factory=list)
    status_events: list[OrderStatusEventResponse] = Field(default_factory=list)


class CreateOrderResponse(BaseModel):
    order: OrderResponse
    transaction_reference_id: str
    checkout_link: str


class OrderSummary(BaseModel):
    id: str
    reference_id: str
    channel: Channel
    status: str
    payment_status: PaymentStatus
    customer_name: str | None
    amount: float | None
    created_at: datetime


class OrderStats(BaseModel):
    active_orders: int
    completed_orders: int
    cancelled_orders: int
    total_order_value: float


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int


class OrderListResponse(BaseModel):
    orders: list[OrderSummary]
    stats: OrderStats
    pagination: PaginationMeta
