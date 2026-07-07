import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_customer, require_owner
from app.api.v1.subscriptions.schemas import (
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    SubscriptionResponse,
)
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.catalog_repository import SubscriptionPlanRepository
from app.repositories.subscription_repository import CustomerSubscriptionRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.payment import PaymentService, get_payment_service
from app.services.subscription import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def get_subscription_service(
    session: AsyncSession = Depends(get_db_session),
    nomba_payment: PaymentService = Depends(get_payment_service),
) -> SubscriptionService:
    return SubscriptionService(
        BusinessRepository(session),
        CustomerSubscriptionRepository(session),
        SubscriptionPlanRepository(session),
        TransactionRepository(session),
        nomba_payment,
    )


@router.post(
    "",
    response_model=CreateSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to a plan and initiate payment via checkout link",
)
async def create_subscription(
    body: CreateSubscriptionRequest,
    customer: User = Depends(require_customer),
    svc: SubscriptionService = Depends(get_subscription_service),
):
    result = await svc.create_subscription(customer, body.plan_id, body.customer_email)

    return CreateSubscriptionResponse(
        subscription=SubscriptionResponse(**result["subscription"]),
        transaction_reference_id=result["transaction_reference_id"],
        checkout_link=result["checkout_link"],
    )


@router.get(
    "/me",
    response_model=list[SubscriptionResponse],
    summary="Get all subscriptions for the authenticated customer",
)
async def get_my_subscriptions(
    active_only: bool = Query(default=False),
    customer: User = Depends(require_customer),
    svc: SubscriptionService = Depends(get_subscription_service),
):
    results = await svc.get_subscriptions_for_customer(customer, active_only=active_only)
    return [SubscriptionResponse(**r) for r in results]


@router.get(
    "",
    response_model=list[SubscriptionResponse],
    summary="Get all subscriptions for the owner's business",
)
async def get_business_subscriptions(
    active_only: bool = Query(default=False),
    owner: User = Depends(require_owner),
    svc: SubscriptionService = Depends(get_subscription_service),
):
    results = await svc.get_subscriptions_for_business(owner, active_only=active_only)
    return [SubscriptionResponse(**r) for r in results]


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get a subscription by ID (the subscribing customer or the business owner)",
)
async def get_subscription(
    subscription_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SubscriptionService = Depends(get_subscription_service),
):
    result = await svc.get_subscription_by_id(current_user, subscription_id)
    return SubscriptionResponse(**result)
