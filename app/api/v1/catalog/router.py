import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.catalog.schemas import (
    CategoryResponse,
    CreateCategoryRequest,
    CreatePriceListItemRequest,
    CreateSubscriptionPlanRequest,
    PriceListItemResponse,
    SubscriptionPlanResponse,
    UpdatePriceListItemRequest,
    UpdateSubscriptionPlanRequest,
)
from app.api.v1.schema import SuccessResponse
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.catalog_repository import (
    CategoryRepository,
    PriceListItemRepository,
    SubscriptionPlanRepository,
)
from app.services.catalog.service import CatalogService

router = APIRouter(prefix="/catalog", tags=["Catalog"])


def get_catalog_service(
    session: AsyncSession = Depends(get_db_session)
) -> CatalogService:
    return CatalogService(
        BusinessRepository(session),
        CategoryRepository(session),
        PriceListItemRepository(session),
        SubscriptionPlanRepository(session),
    )

@router.post(
    "/categories",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category for the owner's business",
)
async def create_category(
    body: CreateCategoryRequest,
    svc: CatalogService = Depends(get_catalog_service),
    owner: User = Depends(require_owner),
):
    result = await svc.create_category(owner, body.name)

    return SuccessResponse(
        data = CategoryResponse(**result),
        message="Category created successfully",
        code=status.HTTP_201_CREATED,
    )


@router.get(
    "/{business_id}/categories",
    response_model=list[CategoryResponse],
    summary="Get all categories for a business (public)",
)
async def get_categories(
    business_id: uuid.UUID,
    svc: CatalogService = Depends(get_catalog_service),
):
    result = await svc.get_categories_by_business(business_id)

    categories = [CategoryResponse.model_validate(r) for r in result]

    return categories

@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (blocked if price list items are attached)",
)
async def delete_category(
    category_id: uuid.UUID,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service)
):

    await svc.delete_catalog_item(owner, "category", category_id)

@router.post(
    "/items",
    response_model=PriceListItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a price list item",
)
async def create_item(
    body: CreatePriceListItemRequest,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):
    result = await svc.create_price_list_item(
        owner,
        body.name,
        body.unit,
        body.price,
        body.category_id,
        body.service_types,
        body.turnaround_hours,
        body.description,
    )

    return PriceListItemResponse(**result)


@router.patch(
    "/items/{item_id}",
    response_model=PriceListItemResponse,
    summary="Update a price list item",
)
async def update_item(
    item_id: uuid.UUID,
    body: UpdatePriceListItemRequest,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):
    result = await svc.update_price_list_item(
        owner,
        item_id,
        body
    )

    return PriceListItemResponse(**result)


@router.patch(
    "/items/{item_id}/toggle",
    response_model=PriceListItemResponse,
    summary="Toggle a price list item active/inactive",
)
async def toggle_item(
    item_id: uuid.UUID,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):
    result = await svc.toggle_price_list_item_active_or_inactive(owner, item_id)

    return PriceListItemResponse(**result)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a price list item",
)
async def delete_item(
    item_id: uuid.UUID,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):
    await svc.delete_catalog_item(owner, "price_list_item", item_id)


@router.get(
    "/{business_id}/items",
    response_model=list[PriceListItemResponse],
    summary="Get price list items for a business (public)",
)
async def get_items(
    business_id: uuid.UUID,
    category_id: uuid.UUID | None = Query(default=None),
    service_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    svc: CatalogService = Depends(get_catalog_service),
):

    results = await svc.get_price_list_items(
        business_id,
        category_id,
        service_type,
        search,
        include_inactive,
    )

    return [_item_resp(r) for r in results]


@router.post(
    "/plans",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a subscription plan",
)
async def create_plan(
    body: CreateSubscriptionPlanRequest,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):
    plan = await svc.create_subscription_plan(
        owner,
        body.name,
        body.price,
        body.billing_cycle,
        body.cancel_policy,
        body.description,
        body.item_cap,
        body.eligible_category_ids,
    )

    return SubscriptionPlanResponse(**plan)


@router.patch(
    "/plans/{plan_id}",
    response_model=SubscriptionPlanResponse,
    summary="Update a subscription plan (creates a new version, preserving subscriber terms)",
)
async def update_plan(
    plan_id: uuid.UUID,
    body: UpdateSubscriptionPlanRequest,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):
    new_plan = await svc.update_subscription_plan(
        owner,
        plan_id,
        body
    )

    return SubscriptionPlanResponse(**new_plan)


@router.delete(
    "/plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete (deactivate) a subscription plan",
)
async def delete_plan(
    plan_id: uuid.UUID,
    owner: User = Depends(require_owner),
    svc: CatalogService = Depends(get_catalog_service),
):

    await svc.delete_catalog_item(owner, "subscription_plan", plan_id)

@router.get(
    "/plans",
    response_model=list[SubscriptionPlanResponse],
    summary="Get all latest subscription plans across every business (public)",
)
async def get_all_plans(
    svc: CatalogService = Depends(get_catalog_service),
):
    plans = await svc.get_all_subscription_plans()
    return [_plan_resp(p) for p in plans]


@router.get(
    "/{business_id}/plans",
    response_model=list[SubscriptionPlanResponse],
    summary="Get latest subscription plans for a business (public)",
)
async def get_plans_for_business(
    business_id: uuid.UUID,
    svc: CatalogService = Depends(get_catalog_service),
):
    plans = await svc.get_all_subscription_plans(business_id)
    return [_plan_resp(p) for p in plans]


@router.get(
    "/plans/{plan_id}",
    response_model=SubscriptionPlanResponse,
    summary="Get a single subscription plan by ID (public)",
)
async def get_plan(
    plan_id: uuid.UUID,
    svc: CatalogService = Depends(get_catalog_service),
):
    plan = await svc.get_subscription_plan_by_id(plan_id)

    return SubscriptionPlanResponse(**plan)


def _cat_resp(c) -> CategoryResponse:
    return CategoryResponse(
        id=str(c.id),
        business_id=str(c.business_id),
        name=c.name,
        created_at=c.created_at,
    )


def _item_resp(i) -> PriceListItemResponse:
    return PriceListItemResponse(
        id=str(i.id),
        business_id=str(i.business_id),
        category_id=str(i.category_id) if i.category_id else None,
        name=i.name,
        service_types=i.service_types or [],
        unit=i.unit,
        price=float(i.price),
        turnaround_hours=i.turnaround_hours,
        description=i.description,
        is_active=i.is_active,
        created_at=i.created_at,
    )


def _plan_resp(p) -> SubscriptionPlanResponse:
    return SubscriptionPlanResponse(
        id=str(p.id),
        business_id=str(p.business_id),
        name=p.name,
        description=p.description,
        price=float(p.price),
        billing_cycle=p.billing_cycle,
        item_cap=p.item_cap,
        eligible_category_ids=[str(cid) for cid in (p.eligible_category_ids or [])],
        cancel_policy=p.cancel_policy,
        is_active=p.is_active,
        created_at=p.created_at,
    )
