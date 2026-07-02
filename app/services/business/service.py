import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from fastapi import HTTPException, status

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
        cac_registration_number: str,
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

        cac_taken = await self._repo.get_by_cac(cac_registration_number)
        if cac_taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A business with this CAC registration number already exists.",
            )

        full_address = f"{address}, {city}, {state}, Nigeria"
        latitude, longitude = get_location(full_address)

        location = None
        if latitude is not None and longitude is not None:
            # TODO: to use in getting businesses by location
            location = from_shape(Point(longitude, latitude), srid=4326)

        business = await self._repo.create(
            owner_user_id=owner_user_id,
            name=name,
            cac_registration_number=cac_registration_number,
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
