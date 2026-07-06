from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.compliance.schemas import KYC_ID_TYPES, KybStatusResponse, KycStatusResponse, SubmitKybRequest, \
    SubmitKycRequest
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.compliance_repository import KybRepository, KycRepository
from app.services.compliance import ComplianceService

router = APIRouter(prefix="/compliance", tags=["Compliance"])


def _get_compliance_service(
    session: AsyncSession = Depends(get_db_session),
) -> ComplianceService:
    return ComplianceService(KycRepository(session), KybRepository(session), BusinessRepository(session),)


@router.post(
    "/kyc",
    response_model=KycStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit KYC verification documents (owner only)",
)
async def submit_kyc(
    body: SubmitKycRequest,
    current_user: User = Depends(require_owner),
    svc: ComplianceService = Depends(_get_compliance_service),
):
    if body.id_type not in KYC_ID_TYPES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"id_type must be one of: {', '.join(sorted(KYC_ID_TYPES))}",
        )

    record = await svc.submit_kyc(
        user_id=current_user.id,
        id_type=body.id_type,
        id_number=body.id_number,
        document_url=body.id_document,
    )
    return _to_response(record)


@router.get(
    "/kyc",
    response_model=KycStatusResponse,
    summary="Get current KYC submission status (owner only)",
)
async def get_kyc_status(
    current_user: User = Depends(require_owner),
    svc: ComplianceService = Depends(_get_compliance_service),
):
    record = await svc.get_kyc_status(current_user.id)
    return _to_response(record)

@router.post(
    "/{business_id}/kyb",
    response_model=KybStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit KYB verification documents (business only)",
)
async def submit_kyb(
    body: SubmitKybRequest,
    owner: User = Depends(require_owner),
    svc: ComplianceService = Depends(_get_compliance_service),
):

    record = await svc.submit_kyb(
        owner_id=owner.id,
        proof_of_address=body.proof_of_address,
        cac_registration_number=body.cac_registration_number,
        business_premises_photos=body.business_premises_photos,
    )
    return _to_kyb_response(record)


@router.get(
    "/kyb",
    response_model=KybStatusResponse,
    summary="Get current KYB submission status (business only)",
)
async def get_kyc_status(
    owner: User = Depends(require_owner),
    svc: ComplianceService = Depends(_get_compliance_service),
):
    record = await svc.get_kyb_status(owner.id)
    return _to_kyb_response(record)

def _to_response(record) -> KycStatusResponse:
    return KycStatusResponse(
        id=record.id,
        user_id=str(record.user_id),
        id_type=record.id_type,
        id_number=record.id_number,
        document_url=record.document_url,
        status=record.status,
        rejection_reason=record.rejection_reason,
        verified_at=record.verified_at,
        created_at=record.created_at,
    )

def _to_kyb_response(record) -> KybStatusResponse:
    return KybStatusResponse(
        id=record.id,
        business_id=str(record.business_id),
        cac_registration_number=record.cac_registration_number,
        proof_of_address=record.proof_of_address,
        business_premises_photos=record.business_premises_photos or [],
        status=record.status,
        verified_at=record.verified_at,
        created_at=record.created_at,
    )
