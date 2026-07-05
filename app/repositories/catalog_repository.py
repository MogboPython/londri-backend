import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, PriceListItem, SubscriptionPlan
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_business(self, business_id: uuid.UUID) -> list[Category]:
        return await self.get_many_by(business_id=business_id)

    async def get_names_by_ids(
        self, business_id: uuid.UUID, category_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        if not category_ids:
            return {}

        result = await self._session.execute(
            select(Category.id, Category.name).where(
                Category.business_id == business_id,
                Category.id.in_(category_ids),
            )
        )
        return {row.id: row.name for row in result.all()}

    async def has_items(self, category_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(func.count()).where(PriceListItem.category_id == category_id)
        )
        return result.scalar_one() > 0


class PriceListItemRepository(BaseRepository[PriceListItem]):
    model = PriceListItem

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def search(
        self,
        business_id: uuid.UUID,
        *,
        category_id: uuid.UUID | None = None,
        service_type: str | None = None,
        name_query: str | None = None,
        active_only: bool = True,
    ) -> list[PriceListItem]:
        stmt = select(PriceListItem).where(PriceListItem.business_id == business_id)

        if active_only:
            stmt = stmt.where(PriceListItem.is_active == True)
        if category_id:
            stmt = stmt.where(PriceListItem.category_id == category_id)
        if service_type:
            # ARRAY @> ARRAY operator: column contains the value
            stmt = stmt.where(PriceListItem.service_types.contains([service_type]))
        if name_query:
            stmt = stmt.where(PriceListItem.name.ilike(f"%{name_query}%"))

        result = await self._session.execute(stmt.order_by(PriceListItem.name))
        return list(result.scalars().all())


class SubscriptionPlanRepository(BaseRepository[SubscriptionPlan]):
    model = SubscriptionPlan

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_plan(self):
        pass

    async def get_latest_for_business(
        self, business_id: uuid.UUID, *, active_only: bool = True
    ) -> list[SubscriptionPlan]:
        """
        Returns the leaf (latest) version of each plan family for a business.
        A plan is the latest if it is the highest version of the group.
        """
        stmt = (
            select(SubscriptionPlan)
            .where(SubscriptionPlan.business_id == business_id)
        )

        if active_only:
            stmt = stmt.where(SubscriptionPlan.is_active == True)

        stmt = stmt.distinct(SubscriptionPlan.plan_group_id).order_by(
            SubscriptionPlan.plan_group_id,
            SubscriptionPlan.version.desc()
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_all(self, *, active_only: bool = True) -> list[SubscriptionPlan]:
        """All latest-version plans across every business (for platform-wide listing)."""
        stmt = select(SubscriptionPlan)

        if active_only:
            stmt = stmt.where(SubscriptionPlan.is_active == True)

        stmt = stmt.distinct(SubscriptionPlan.plan_group_id).order_by(
            SubscriptionPlan.plan_group_id,
            SubscriptionPlan.version.desc()
        )

        result = await self._session.execute(stmt.order_by(SubscriptionPlan.created_at.desc()))
        return list(result.scalars().all())
