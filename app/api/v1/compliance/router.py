from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.v1.compliance.schemas import KycStatusResponse, SubmitKycRequest, KYC_ID_TYPES
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.compliance_repository import KycRepository
from app.services.compliance.service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["Compliance"])


def _get_compliance_service(
    session: AsyncSession = Depends(get_db_session),
) -> ComplianceService:
    return ComplianceService(KycRepository(session))


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
