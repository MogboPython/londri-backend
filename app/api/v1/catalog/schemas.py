import uuid
from datetime import datetime

from pydantic import BaseModel, Field

class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class CategoryResponse(BaseModel):
    id: str
    business_id: str
    name: str
    created_at: datetime

class CreatePriceListItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    service_types: list[str] = Field(default_factory=list)
    unit: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., gt=0)
    turnaround_hours: int | None = Field(default=None, gt=0)
    description: str | None = None


class UpdatePriceListItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    service_types: list[str] | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    price: float | None = Field(default=None, gt=0)
    turnaround_hours: int | None = Field(default=None, gt=0)
    description: str | None = None


class PriceListItemResponse(BaseModel):
    id: str
    business_id: str | None = None
    name: str
    updated_at: datetime | None = None
    message: str | None = None
    category_id: str | None = None
    name: str
    service_types: list[str]
    unit: str
    price: float
    turnaround_hours: int | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime | None = None


class CreateSubscriptionPlanRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: float = Field(..., gt=0)
    billing_cycle: str = Field(..., pattern="^(weekly|monthly)$")
    item_cap: int = Field(default=0, ge=0)
    eligible_category_ids: list[uuid.UUID] = Field(default_factory=list)
    cancel_policy: str = Field(default="at_period_end", pattern="^(immediately|at_period_end)$")


class UpdateSubscriptionPlanRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    billing_cycle: str | None = Field(default=None, pattern="^(weekly|monthly)$")
    item_cap: int | None = Field(default=None, ge=0)
    eligible_category_ids: list[uuid.UUID] | None = None
    cancel_policy: str | None = Field(default=None, pattern="^(immediately|at_period_end)$")


class SubscriptionPlanResponse(BaseModel):
    id: str
    business_id: str | None = None
    name: str
    description: str | None
    price: float
    billing_cycle: str
    item_cap: int
    eligible_categories: list[str] = Field(default_factory=list)
    cancel_policy: str
    is_active: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
