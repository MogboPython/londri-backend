import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import CustomerSubscription, SubscriptionStatus
from app.repositories.base import BaseRepository


class CustomerSubscriptionRepository(BaseRepository[CustomerSubscription]):
    model = CustomerSubscription

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_customer(
        self, customer_id: uuid.UUID, *, active_only: bool = False
    ) -> list[CustomerSubscription]:
        stmt = select(CustomerSubscription).where(CustomerSubscription.customer_id == customer_id)
        if active_only:
            stmt = stmt.where(CustomerSubscription.status == SubscriptionStatus.active)
        stmt = stmt.order_by(CustomerSubscription.created_at.desc())

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_business(
        self, business_id: uuid.UUID, *, active_only: bool = False
    ) -> list[CustomerSubscription]:
        stmt = select(CustomerSubscription).where(CustomerSubscription.business_id == business_id)
        if active_only:
            stmt = stmt.where(CustomerSubscription.status == SubscriptionStatus.active)
        stmt = stmt.order_by(CustomerSubscription.created_at.desc())

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_customer_and_business(
        self, customer_id: uuid.UUID, business_id: uuid.UUID
    ) -> CustomerSubscription | None:
        """Most recent subscription this customer has had with this business."""
        stmt = (
            select(CustomerSubscription)
            .where(
                CustomerSubscription.customer_id == customer_id,
                CustomerSubscription.business_id == business_id,
            )
            .order_by(CustomerSubscription.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
