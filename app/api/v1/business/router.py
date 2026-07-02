from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.business.schemas import BusinessResponse, CreateBusinessRequest
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.services.business.service import BusinessService
from app.core.session import get_db_session

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
        cac_registration_number=body.cac_registration_number,
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

def _to_response(business) -> BusinessResponse:
    return BusinessResponse(
        id=str(business.id),
        name=business.name,
        cac_registration_number=business.cac_registration_number,
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
