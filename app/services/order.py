import random
import string
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status

from app.models.order import Channel, Order, OrderItem, OrderStatus, PaymentStatus
from app.models.user import User
from app.repositories.accounts_repository import BusinessSubaccountRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.catalog_repository import PriceListItemRepository
from app.repositories.order_repository import OrderRepository, OrderStatusEventRepository
from app.repositories.transaction_repository import TransactionRepository
from app.util.periods import Period, resolve_period_range

from .payment import PaymentService


class OrderService:
    def __init__(
            self,
            business_repo: BusinessRepository,
            order_repo: OrderRepository,
            status_event_repo: OrderStatusEventRepository,
            txn_repo: TransactionRepository,
            price_list_repo: PriceListItemRepository,
            subaccount_repo: BusinessSubaccountRepository,
            nomba_payment: PaymentService,
    ) -> None:
        self._business_repo = business_repo
        self._order_repo = order_repo
        self._status_event_repo = status_event_repo
        self._txn_repo = txn_repo
        self._price_list_repo = price_list_repo
        self._subaccount_repo = subaccount_repo
        self._nomba_payment = nomba_payment

    async def _resolve_business(self, owner: User) -> uuid.UUID:
        business = await self._business_repo.get_by_owner(owner.id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business registered for this account.",
            )
        return business.id

    async def _generate_order_reference(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        while True:
            candidate = f"LDR-{today}-{random.randint(0, 9999):04d}"
            if not await self._order_repo.get_by_reference_id(candidate):
                return candidate

    async def _generate_transaction_reference(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        while True:
            letters = "".join(random.choices(string.ascii_uppercase, k=3))
            digits = f"{random.randint(0, 999):03d}"
            candidate = f"PAY-{today}-{letters}{digits}"
            if not await self._txn_repo.get_by_reference_id(candidate):
                return candidate

    @staticmethod
    def _order_item_to_dict(item) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "price_list_item_id": str(item.price_list_item_id) if item.price_list_item_id else None,
            "item_name": item.item_name,
            "service_types": item.service_types or [],
            "unit": item.unit,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "line_total": float(item.line_total),
        }

    def _order_to_dict(self, order: Order) -> dict[str, Any]:
        return {
            "id": str(order.id),
            "business_id": str(order.business_id),
            "reference_id": order.reference_id,
            "channel": order.channel,
            "status": order.status,
            "payment_status": order.payment_status,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "customer_whatsapp": order.customer_whatsapp,
            "to_be_delivered": order.to_be_delivered,
            "delivery_address": order.delivery_address,
            "notes": order.notes,
            "amount": float(order.amount) if order.amount is not None else None,
            "scheduled_pickup_at": order.scheduled_pickup_at,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": [self._order_item_to_dict(i) for i in order.items],
            "status_events": [
                {
                    "id": str(e.id),
                    "from_status": e.from_status,
                    "to_status": e.to_status,
                    "actor_id": str(e.actor_id) if e.actor_id else None,
                    "actor_role": e.actor_role,
                    "note": e.note,
                    "timestamp": e.timestamp,
                }
                for e in order.status_events
            ],
        }

    # TODO: owner can make order and send payment link to customer later
    async def create_order(
            self,
            business_id: uuid.UUID,
            customer: User | None,
            items: list[dict[str, Any]],
            channel: Channel,
            customer_name: str | None,
            customer_email: str,
            customer_whatsapp: str | None,
            to_be_delivered: bool,
            delivery_address: str | None,
            notes: str | None,
            scheduled_pickup_at: datetime | None,
    ) -> dict[str, Any]:
        business = await self._business_repo.get_by_id(business_id)
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")

        subaccount = await self._subaccount_repo.get_by_business(business_id)
        if not subaccount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This business has not completed payment setup.",
            )

        order_items = []
        total = Decimal("0")
        for entry in items:
            price_list_item_id = entry["price_list_item_id"]
            quantity = Decimal(str(entry["quantity"]))

            price_list_item = await self._price_list_repo.get_by_id(price_list_item_id)
            if not price_list_item or price_list_item.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Price list item {price_list_item_id} not found for this business.",
                )

            unit_price = Decimal(str(price_list_item.price))
            line_total = (unit_price * quantity).quantize(Decimal("0.01"))
            total += line_total

            order_items.append(
                {
                    "price_list_item_id": price_list_item.id,
                    "item_name": price_list_item.name,
                    "service_types": price_list_item.service_types or [],
                    "unit": price_list_item.unit,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

        reference_id = await self._generate_order_reference()

        order = await self._order_repo.create(
            business_id=business_id,
            customer_id=customer.id if customer else None,
            reference_id=reference_id,
            channel=channel,
            status=OrderStatus.requested.value,
            payment_status=PaymentStatus.pending,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_whatsapp=customer_whatsapp,
            to_be_delivered=to_be_delivered,
            delivery_address=delivery_address,
            notes=notes,
            amount=total,
            scheduled_pickup_at=scheduled_pickup_at,
            items=[OrderItem(**oi) for oi in order_items],
        )

        transaction_reference = await self._generate_transaction_reference()
        transaction = await self._txn_repo.create(
            business_id=business_id,
            order_id=order.id,
            reference_id=transaction_reference,
            merchant_tx_ref=str(order.id),
            amount=total,
            currency="NGN",
        )

        charge = await self._nomba_payment.create_charge(
            amount=int(total),
            customer_email=customer_email,
            subaccount_id=subaccount.provider_subaccount_id,
            order_reference=str(order.id),
            metadata={
                "order_reference_id": order.reference_id,
                "transaction_reference_id": transaction.reference_id,
                "operation": "order_payment",
            },
        )

        return {
            "order": self._order_to_dict(order),
            "transaction_reference_id": transaction.reference_id,
            "checkout_link": charge["checkout_link"],
        }

    async def update_order_status(
            self,
            owner: User,
            order_id: uuid.UUID,
            new_status: OrderStatus,
            note: str | None,
    ) -> dict[str, Any]:
        business_id = await self._resolve_business(owner)

        order = await self._order_repo.get_by_id(order_id)
        if not order or order.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

        from_status = order.status
        await self._order_repo.update_instance(order, status=new_status.value)

        await self._status_event_repo.create(
            order_id=order.id,
            from_status=from_status,
            to_status=new_status.value,
            actor_id=owner.id,
            actor_role=owner.role,
            note=note,
        )

        updated_order = await self._order_repo.get_with_details(order_id)
        # TODO: send whatsapp message or mail to customer
        return self._order_to_dict(updated_order)

    async def get_order_by_id(self, owner: User, order_id: uuid.UUID) -> dict[str, Any]:
        business_id = await self._resolve_business(owner)

        order = await self._order_repo.get_with_details(order_id)
        if not order or order.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

        return self._order_to_dict(order)

    async def get_orders(
            self,
            owner: User,
            *,
            order_status: OrderStatus | None = None,
            payment_status: PaymentStatus | None = None,
            channel: Channel | None = None,
            reference_id: str | None = None,
            period: Period = Period.this_month,
            start_date: date | None = None,
            end_date: date | None = None,
            limit: int = 20,
            offset: int = 0,
    ) -> dict[str, Any]:
        business_id = await self._resolve_business(owner)
        range_start, range_end = resolve_period_range(period, start_date, end_date)

        orders = await self._order_repo.search(
            business_id,
            status=order_status,
            payment_status=payment_status,
            channel=channel,
            reference_id=reference_id,
            start_date=range_start,
            end_date=range_end,
            limit=limit,
            offset=offset,
        )
        total = await self._order_repo.count_search(
            business_id,
            status=order_status,
            payment_status=payment_status,
            channel=channel,
            reference_id=reference_id,
            start_date=range_start,
            end_date=range_end,
        )
        stats = await self._order_repo.get_stats(business_id, range_start, range_end)

        return {
            "orders": orders,
            "total": total,
            "stats": stats,
        }
