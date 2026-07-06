import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus, OrderStatusEvent
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_reference_id(self, reference_id: str) -> Order | None:
        return await self.get_one_by(reference_id=reference_id)

    async def get_with_details(self, order_id: uuid.UUID) -> Order | None:
        result = await self._session.execute(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.status_events))
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _apply_filters(
        stmt: Select,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        payment_status: str | None = None,
        channel: str | None = None,
        reference_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Select:
        stmt = stmt.where(Order.business_id == business_id)
        if status:
            stmt = stmt.where(Order.status == status)
        if payment_status:
            stmt = stmt.where(Order.payment_status == payment_status)
        if channel:
            stmt = stmt.where(Order.channel == channel)
        if reference_id:
            stmt = stmt.where(Order.reference_id.ilike(f"%{reference_id}%"))
        if start_date:
            stmt = stmt.where(Order.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Order.created_at <= end_date)
        return stmt

    async def search(
        self,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        payment_status: str | None = None,
        channel: str | None = None,
        reference_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Order]:
        stmt = self._apply_filters(
            select(Order),
            business_id,
            status=status,
            payment_status=payment_status,
            channel=channel,
            reference_id=reference_id,
            start_date=start_date,
            end_date=end_date,
        )
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_search(
        self,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        payment_status: str | None = None,
        channel: str | None = None,
        reference_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        stmt = self._apply_filters(
            select(func.count(Order.id)),
            business_id,
            status=status,
            payment_status=payment_status,
            channel=channel,
            reference_id=reference_id,
            start_date=start_date,
            end_date=end_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_stats(
        self,
        business_id: uuid.UUID,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> dict[str, Any]:
        stmt = select(
            func.count(Order.id)
            .filter(Order.status.notin_([OrderStatus.completed, OrderStatus.cancelled]))
            .label("active"),
            func.count(Order.id).filter(Order.status == OrderStatus.completed).label("completed"),
            func.count(Order.id).filter(Order.status == OrderStatus.cancelled).label("cancelled"),
            func.coalesce(func.sum(Order.amount), 0).label("total_value"),
        ).where(Order.business_id == business_id)

        if start_date:
            stmt = stmt.where(Order.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Order.created_at <= end_date)

        result = await self._session.execute(stmt)
        row = result.one()
        return {
            "active_orders": row.active,
            "completed_orders": row.completed,
            "cancelled_orders": row.cancelled,
            "total_order_value": float(row.total_value),
        }


class OrderStatusEventRepository(BaseRepository[OrderStatusEvent]):
    model = OrderStatusEvent

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_order(self, order_id: uuid.UUID) -> list[OrderStatusEvent]:
        result = await self._session.execute(
            select(OrderStatusEvent)
            .where(OrderStatusEvent.order_id == order_id)
            .order_by(OrderStatusEvent.timestamp)
        )
        return list(result.scalars().all())
