import uuid
from typing import Sequence

from geoalchemy2.functions import ST_DWithin
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from app.models.business import Business
from app.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[Business]):
    model = Business

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_owner(self, owner_user_id: uuid.UUID) -> Business | None:
        result = await self._session.execute(
            select(Business)
            .options(selectinload(Business.kyb_verifications))
            .where(Business.owner_user_id == owner_user_id)
        )
        return result.scalar_one_or_none()

    async def get_with_subaccount_details(self, business_id: uuid.UUID) -> Business | None:
        result = await self._session.execute(
            select(Business)
            .options(selectinload(Business.subaccounts))
            .where(Business.id == business_id)
        )
        return result.scalar_one_or_none()

    # async def get_by_cac(self, cac_registration_number: str) -> Business | None:
    #     return await self.get_one_by(cac_registration_number=cac_registration_number)

    async def discover(
        self,
        *,
        city: str | None = None,
        state: str | None = None,
        name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 10.0,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Business]:
        stmt = (
            select(Business)
            .where(Business.is_discoverable == True)  # noqa: E712
        )

        if city:
            stmt = stmt.where(Business.city.ilike(f"%{city}%"))
        if state:
            stmt = stmt.where(Business.state.ilike(f"%{state}%"))
        if name:
            stmt = stmt.where(Business.name.ilike(f"%{name}%"))
        if latitude is not None and longitude is not None:
            point = func.ST_GeographyFromText(f"SRID=4326;POINT({longitude} {latitude})")
            stmt = stmt.where(
                ST_DWithin(Business.location, point, radius_km * 1000)
            )

        result = await self._session.execute(
            stmt.order_by(Business.name).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
