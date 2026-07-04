from datetime import datetime

from pydantic import BaseModel, Field


KYC_ID_TYPES = frozenset(
    {"national_id", "drivers_license", "voters_card", "international_passport"}
)

class SubmitKycRequest(BaseModel):
    bvn: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    id_type: str = Field(
        ...,
        description=(
            "One of: national_id, drivers_license, voters_card, international_passport"
        ),
    )
    id_number: str = Field(..., min_length=2, max_length=255)
    id_document: str = Field(
        ...,
        description="Publicly accessible URL of the uploaded ID document image/PDF",
    )

    def validate_id_type(self) -> None:
        if self.id_type not in KYC_ID_TYPES:
            raise ValueError(
                f"id_type must be one of: {', '.join(sorted(KYC_ID_TYPES))}"
            )


class KycStatusResponse(BaseModel):
    id: int
    user_id: str
    id_type: str
    id_number: str
    document_url: str | None
    status: str
    rejection_reason: str | None
    verified_at: datetime | None
    created_at: datetime

class SubmitKybRequest(BaseModel):
    cac_registration_number: str = Field(..., min_length=2, max_length=255)
    proof_of_address: str = Field(
        ...,
        description="Publicly accessible URL of the uploaded ID document image/PDF",
    )
    business_premises_photos: list[str] = Field(
        default_factory=list,
        description="Publicly accessible URLs of the uploaded images",
    )

class KybStatusResponse(BaseModel):
    id: int
    business_id: str
    cac_registration_number: str
    proof_of_address: str
    business_premises_photos: list[str]
    status: str
    verified_at: datetime | None
    created_at: datetime