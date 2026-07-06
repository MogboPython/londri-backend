import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.orders.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderListResponse,
    OrderResponse,
    OrderStats,
    OrderSummary,
    PaginationMeta,
    UpdateOrderStatusRequest,
)
from app.core.session import get_db_session
from app.models.order import Channel, Order, OrderStatus, PaymentStatus
from app.models.user import User
from app.repositories.accounts_repository import BusinessSubaccountRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.catalog_repository import PriceListItemRepository
from app.repositories.order_repository import OrderRepository, OrderStatusEventRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.order import OrderService
from app.services.payment import PaymentService, get_payment_service
from app.services.whatsapp import WhatsAppService, get_whatsapp_service
from app.util.periods import Period

router = APIRouter(prefix="/orders", tags=["Orders"])


def get_order_service(
    session: AsyncSession = Depends(get_db_session),
    nomba_payment: PaymentService = Depends(get_payment_service),
    whatsapp: WhatsAppService = Depends(get_whatsapp_service),
) -> OrderService:
    return OrderService(
        BusinessRepository(session),
        OrderRepository(session),
        OrderStatusEventRepository(session),
        TransactionRepository(session),
        PriceListItemRepository(session),
        BusinessSubaccountRepository(session),
        nomba_payment,
        whatsapp,
    )


@router.post(
    "",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order and initiate payment via checkout link",
)
async def create_order(
    body: CreateOrderRequest,
    background_tasks: BackgroundTasks,
    svc: OrderService = Depends(get_order_service),
):
    result = await svc.create_order(
        background_tasks,
        business_id=body.business_id,
        items=[item.model_dump() for item in body.items],
        channel=body.channel,
        customer_name=body.customer_name,
        customer_email=str(body.customer_email),
        customer_whatsapp=body.customer_whatsapp,
        to_be_delivered=body.to_be_delivered,
        delivery_address=body.delivery_address,
        notes=body.notes,
        scheduled_pickup_at=body.scheduled_pickup_at,
    )

    return CreateOrderResponse(
        order=OrderResponse(**result["order"]),
        transaction_reference_id=result["transaction_reference_id"],
        checkout_link=result["checkout_link"],
    )


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update an order's status (owner only) — tracked via OrderStatusEvent",
)
async def update_order_status(
    background_tasks: BackgroundTasks,
    order_id: uuid.UUID,
    body: UpdateOrderStatusRequest,
    owner: User = Depends(require_owner),
    svc: OrderService = Depends(get_order_service),
):
    result = await svc.update_order_status(background_tasks, owner, order_id, body.status, body.note)
    return OrderResponse(**result)


@router.get(
    "",
    response_model=OrderListResponse,
    summary="Get all orders for the owner's business, with stats and pagination",
)
async def get_orders(
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    payment_status: PaymentStatus | None = Query(default=None),
    channel: Channel | None = Query(default=None),
    reference_id: str | None = Query(default=None),
    period: Period = Query(default=Period.this_month),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=20, gt=0, le=100),
    offset: int = Query(default=0, ge=0),
    owner: User = Depends(require_owner),
    svc: OrderService = Depends(get_order_service),
):
    result = await svc.get_orders(
        owner,
        order_status=order_status,
        payment_status=payment_status,
        channel=channel,
        reference_id=reference_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return OrderListResponse(
        orders=[_order_summary(o) for o in result["orders"]],
        stats=OrderStats(**result["stats"]),
        pagination=PaginationMeta(total=result["total"], limit=limit, offset=offset),
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get an order by ID (owner only)",
)
async def get_order(
    order_id: uuid.UUID,
    owner: User = Depends(require_owner),
    svc: OrderService = Depends(get_order_service),
):
    result = await svc.get_order_by_id(owner, order_id)
    return OrderResponse(**result)


def _order_summary(order: Order) -> OrderSummary:
    return OrderSummary(
        id=str(order.id),
        reference_id=order.reference_id,
        channel=order.channel,
        status=order.status,
        payment_status=order.payment_status,
        customer_name=order.customer_name,
        amount=float(order.amount) if order.amount is not None else None,
        created_at=order.created_at,
    )
