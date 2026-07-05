import uuid
from typing import Any, List

from fastapi import HTTPException, status

from app.models import PriceListItem, SubscriptionPlan
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.catalog_repository import (
    CategoryRepository,
    PriceListItemRepository,
    SubscriptionPlanRepository,
)


class CatalogService:
    def __init__(
        self,
        business_repo: BusinessRepository,
        category_repo: CategoryRepository,
        price_list_repo: PriceListItemRepository,
        sub_plan_repo: SubscriptionPlanRepository,
    ) -> None:
        self._business_repo = business_repo
        self._category_repo = category_repo
        self._price_list_repo = price_list_repo
        self._sub_plan_repo = sub_plan_repo

    async def _resolve_business(self, owner: User) -> uuid.UUID:
        """Return the owner's business_id or raise 404."""
        business = await self._business_repo.get_by_owner(owner.id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business registered for this account.",
            )
        return business.id

    async def _eligible_category_names(
        self, business_id: uuid.UUID, category_ids: list[uuid.UUID] | None
    ) -> list[str]:
        if not category_ids:
            return []

        name_map = await self._category_repo.get_names_by_ids(business_id, category_ids)
        return [name_map[cid] for cid in category_ids if cid in name_map]

    async def _subscription_plan_to_dict(self, plan: SubscriptionPlan) -> dict:
        return {
            "id": str(plan.id),
            "business_id": str(plan.business_id),
            "name": plan.name,
            "description": plan.description,
            "price": float(plan.price),
            "billing_cycle": plan.billing_cycle,
            "item_cap": plan.item_cap,
            "eligible_categories": await self._eligible_category_names(
                plan.business_id, plan.eligible_category_ids
            ),
            "cancel_policy": plan.cancel_policy,
            "is_active": plan.is_active,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    async def create_category(self, owner: User, name: str) -> dict:
        business_id = await self._resolve_business(owner)

        existing = await self._category_repo.get_one_by(business_id=business_id, name=name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{name}' already exists.",
            )

        cat = await self._category_repo.create(business_id=business_id, name=name)

        return {
            "id": str(cat.id),
            "business_id": str(cat.business_id),
            "name": cat.name,
            "created_at": cat.created_at,
        }

    async def get_categories_by_business(self, business_id: uuid.UUID) -> List[dict]:
        cats = await self._category_repo.get_by_business(business_id)

        categories = [{
            "id": str(cat.id),
            "business_id": str(cat.business_id),
            "name": cat.name,
            "created_at": cat.created_at,
        } for cat in cats]

        return categories

    async def delete_catalog_item(self, owner: User, item: str, item_id: uuid.UUID) -> None:
        business_id = await self._resolve_business(owner)

        match item:
            case "category":
                cat = await self._category_repo.get_by_id(item_id)
                if not cat or cat.business_id != business_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

                if await self._category_repo.has_items(item_id):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot delete a category that has price list items attached.",
                    )

                await self._category_repo.delete_instance(cat)

            case "price_list_item":
                price_list_item = await self._price_list_repo.get_by_id(item_id)
                if not price_list_item or price_list_item.business_id != business_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price list item not found.")

                await self._price_list_repo.delete_instance(price_list_item)

            case "subscription_plan":
                sub_plan = await self._sub_plan_repo.get_by_id(item_id)
                if not sub_plan or sub_plan.business_id != business_id:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")

                await self._sub_plan_repo.delete_instance(sub_plan)

    async def create_price_list_item(
            self,
            owner: User,
            name: str,
            unit: str,
            price: float,
            category_id: uuid.UUID | None = None,
            service_types: list[str] | None = None,
            turnaround_hours: int | None = None,
            description: str | None = None,
    ) -> dict:
        business_id = await self._resolve_business(owner)

        if category_id:
            cat = await self._category_repo.get_by_id(category_id)
            if not cat or cat.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category not found for this business.",
                )

        item = await self._price_list_repo.create(
            business_id=business_id,
            category_id=category_id,
            name=name,
            service_types=service_types,
            unit=unit,
            price=price,
            turnaround_hours=turnaround_hours,
            description=description,
        )
        return {
            "id": str(item.id),
            "business_id": str(item.business_id),
            "category_id": str(item.category_id) if item.category_id else None,
            "name": item.name,
            "service_types": item.service_types or [],
            "unit": item.unit,
            "price": float(item.price),
            "turnaround_hours": item.turnaround_hours,
            "description": item.description,
            "is_active": item.is_active,
            "created_at": item.created_at,
        }

    async def update_price_list_item(
        self,
        owner: User,
        item_id: uuid.UUID,
        body: Any,
    ) -> dict:
        business_id = await self._resolve_business(owner)

        item = await self._price_list_repo.get_by_id(item_id)
        if not item or item.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

        if body.category_id is not None:
            cat = await self._category_repo.get_by_id(body.category_id)
            if not cat or cat.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category not found for this business.",
                )

        updates = body.model_dump(exclude_unset=True)
        item = await self._price_list_repo.update_instance(item, **updates)

        return {
            "id": str(item.id),
            "category_id": str(item.category_id) if item.category_id else None,
            "name": item.name,
            "service_types": item.service_types or [],
            "unit": item.unit,
            "price": float(item.price),
            "turnaround_hours": item.turnaround_hours,
            "description": item.description,
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }

    async def toggle_price_list_item_active_or_inactive(
        self,
        owner: User,
        item_id: uuid.UUID,
    ) -> dict:
        business_id = await self._resolve_business(owner)

        item = await self._price_list_repo.get_by_id(item_id)
        if not item or item.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

        item = await self._price_list_repo.update_instance(item, is_active=not item.is_active)

        return {
            "id": str(item.id),
            "category_id": str(item.category_id) if item.category_id else None,
            "name": item.name,
            "service_types": item.service_types or [],
            "unit": item.unit,
            "price": float(item.price),
            "turnaround_hours": item.turnaround_hours,
            "description": item.description,
            "is_active": item.is_active,
            "updated_at": item.updated_at,
        }

    async def get_price_list_items(
            self,
            business_id: uuid.UUID,
            category_id: uuid.UUID | None = None,
            service_type: str | None = None,
            search: str | None = None,
            include_inactive: bool | None = None,
    ) -> list[PriceListItem]:

        result = await self._price_list_repo.search(
            business_id,
            category_id=category_id,
            service_type=service_type,
            name_query=search,
            active_only=not include_inactive,
        )

        return result

    async def create_subscription_plan(
        self,
            owner: User,
            name: str,
            price: float,
            billing_cycle: str,
            cancel_policy: str,
            description: str | None = None,
            item_cap: int = None,
            eligible_category_ids: list[uuid.UUID] | None = None,
    ) -> dict:

        business_id = await self._resolve_business(owner)

        new_plan_id = uuid.uuid4()
        while await self._sub_plan_repo.get_by_id(new_plan_id) is not None:
            new_plan_id = uuid.uuid4()

        plan = await self._sub_plan_repo.create(
            id=new_plan_id,
            plan_group_id=new_plan_id,
            business_id=business_id,
            name=name,
            description=description,
            price=price,
            billing_cycle=billing_cycle,
            item_cap=item_cap,
            eligible_category_ids=eligible_category_ids,
            cancel_policy=cancel_policy,
            version=1,
            is_active=True,
        )

        return await self._subscription_plan_to_dict(plan)

    async def update_subscription_plan(
            self,
            owner: User,
            plan_id: uuid.UUID,
            body: Any
    ) -> dict:
        business_id = await self._resolve_business(owner)

        old = await self._sub_plan_repo.get_by_id(plan_id)
        if not old or old.business_id != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

        updates = body.model_dump(exclude_unset=True)

        # Deactivate the old version
        await self._sub_plan_repo.update_instance(old, is_active=False)

        # Create new version inheriting unchanged fields from the old one
        new_plan = await self._sub_plan_repo.create(
            business_id=business_id,
            name=updates.get("name", old.name),
            description=updates.get("description", old.description),
            price=updates.get("price", old.price),
            billing_cycle=updates.get("billing_cycle", old.billing_cycle),
            item_cap=updates.get("item_cap", old.item_cap),
            eligible_category_ids=updates.get("eligible_category_ids", old.eligible_category_ids),
            cancel_policy=updates.get("cancel_policy", old.cancel_policy),
            version=old.version + 1,
            plan_group_id=old.id,
            is_active=True,
        )

        return await self._subscription_plan_to_dict(new_plan)

    async def get_all_subscription_plans(
        self, business_id: uuid.UUID | None = None
    ) -> list[dict]:
        if business_id:
            plans = await self._sub_plan_repo.get_latest_for_business(business_id)
        else:
            plans = await self._sub_plan_repo.get_latest_all()

        return [await self._subscription_plan_to_dict(plan) for plan in plans]

    async def get_subscription_plan_by_id(self, plan_id: uuid.UUID) -> dict:
        plan = await self._sub_plan_repo.get_by_id(plan_id)

        if not plan or not plan.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

        return await self._subscription_plan_to_dict(plan)



