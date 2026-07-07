import uuid

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.orm import selectinload

from app.models.business import Business
from app.repositories.business_repository import BusinessRepository
from app.util.locator import get_location


class BusinessService:
    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    async def create_business(
        self,
        owner_user_id: uuid.UUID,
        name: str,
        address: str,
        city: str,
        state: str,
    ) -> Business:
        # One business per owner
        existing = await self._repo.get_by_owner(owner_user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already registered a business.",
            )

        full_address = f"{address}, {city}, {state}, Nigeria"
        latitude, longitude = get_location(full_address)

        location = None
        if latitude is not None and longitude is not None:
            location = from_shape(Point(longitude, latitude), srid=4326)

        business = await self._repo.create(
            owner_user_id=owner_user_id,
            name=name,
            address=address,
            city=city,
            state=state,
            latitude=latitude,
            longitude=longitude,
            location=location,
        )
        return business

    async def get_my_business(self, owner_user_id: uuid.UUID) -> Business:
        business = await self._repo.get_by_owner(owner_user_id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business profile found.",
            )
        return business

    async def find_businesses(
            self,
            city: str | None = None,
            state: str | None = None,
            name: str | None = None,
            lat: float | None = None,
            lng: float | None = None,
            radius_km: float | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Business]:
        businesses = await self._repo.discover(
            city=city,
            state=state,
            name=name,
            latitude=lat,
            longitude=lng,
            radius_km=radius_km,
            limit=limit,
            offset=offset,
        )

        return businesses

    async def get_business(self, business_id: uuid.UUID) -> Business:
        business = await self._repo.get_by_id(business_id)
        if not business or not business.is_discoverable:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")

        return business