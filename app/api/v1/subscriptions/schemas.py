import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.subscription import SubscriptionStatus


class CreateSubscriptionRequest(BaseModel):
    plan_id: uuid.UUID
    customer_email: EmailStr | None = None


class SubscriptionResponse(BaseModel):
    id: str
    business_id: str
    customer_id: str
    plan_id: str
    plan_version: int
    status: SubscriptionStatus
    current_period_start: datetime | None
    current_period_end: datetime | None
    next_billing_date: datetime | None
    items_used_in_current_period: int
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreateSubscriptionResponse(BaseModel):
    subscription: SubscriptionResponse
    transaction_reference_id: str
    checkout_link: str
