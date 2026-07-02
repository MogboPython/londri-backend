from datetime import datetime

from pydantic import BaseModel, Field


class CreateBusinessRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    cac_registration_number: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2, max_length=60)
    state: str = Field(..., min_length=2, max_length=60)


class BusinessResponse(BaseModel):
    id: str
    name: str
    cac_registration_number: str | None
    address: str | None
    city: str | None
    state: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    email: str | None
    logo_url: str | None
    is_active: bool
    is_discoverable: bool
    current_kyb_status: str
    created_at: datetime
