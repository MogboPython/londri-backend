import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.business.schemas import BusinessResponse, BusinessSummary, CreateBusinessRequest
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.services.business.service import BusinessService

router = APIRouter(prefix="/business", tags=["Business"])


def _get_business_service(
    session: AsyncSession = Depends(get_db_session),
) -> BusinessService:
    return BusinessService(BusinessRepository(session))


@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new business (owner only)",
)
async def create_business(
    body: CreateBusinessRequest,
    current_user: User = Depends(require_owner),
    svc: BusinessService = Depends(_get_business_service),
):
    business = await svc.create_business(
        owner_user_id=current_user.id,
        name=body.name,
        address=body.address,
        city=body.city,
        state=body.state,
    )
    return _to_response(business)


@router.get(
    "/me",
    response_model=BusinessResponse,
    summary="Get the authenticated owner's business",
)
async def get_my_business(
    current_user: User = Depends(require_owner),
    svc: BusinessService = Depends(_get_business_service),
):
    business = await svc.get_my_business(current_user.id)
    return _to_response(business)


@router.get(
    "",
    response_model=list[BusinessSummary],
    summary="Discover businesses — filter by city, state, proximity, or name",
)
async def discover_businesses(
    city: str | None = Query(default=None),
    state: str | None = Query(default=None),
    name: str | None = Query(default=None),
    lat: float | None = Query(default=None, description="Latitude for proximity search"),
    lng: float | None = Query(default=None, description="Longitude for proximity search"),
    radius_km: float = Query(default=10.0, gt=0, le=100),
    limit: int = Query(default=20, gt=0, le=100),
    offset: int = Query(default=0, ge=0),
    svc: BusinessService = Depends(_get_business_service),
):
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lat and lng must both be provided for proximity search.",
        )

    businesses = await svc.find_businesses(
        city=city,
        state=state,
        name=name,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )

    return [_to_summary(b) for b in businesses]


@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    summary="Get a business by ID (public)",
)
async def get_business(
    business_id: uuid.UUID,
    svc: BusinessService = Depends(_get_business_service),
):
    business = await svc.get_business(business_id)

    return _to_response(business)

def _to_response(business) -> BusinessResponse:
    return BusinessResponse(
        id=str(business.id),
        name=business.name,
        address=business.address,
        city=business.city,
        state=business.state,
        latitude=float(business.latitude) if business.latitude is not None else None,
        longitude=float(business.longitude) if business.longitude is not None else None,
        phone=business.phone,
        email=business.email,
        logo_url=business.logo_url,
        is_active=business.is_active,
        is_discoverable=business.is_discoverable,
        current_kyb_status=business.current_kyb_status,
        created_at=business.created_at,
    )


def _to_summary(business) -> BusinessSummary:
    return BusinessSummary(
        id=str(business.id),
        name=business.name,
        address=business.address,
        city=business.city,
        state=business.state,
        latitude=float(business.latitude) if business.latitude is not None else None,
        longitude=float(business.longitude) if business.longitude is not None else None,
        phone=business.phone,
        logo_url=business.logo_url,
    )
