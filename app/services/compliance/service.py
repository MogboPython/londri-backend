import uuid

from fastapi import HTTPException, status

from app.models.compliance import KycVerification, VerificationStatus
from app.repositories.compliance_repository import KycRepository


class ComplianceService:
    def __init__(self, kyc_repo: KycRepository) -> None:
        self._kyc = kyc_repo

    async def submit_kyc(
        self,
        user_id: uuid.UUID,
        id_type: str,
        id_number: str,
        document_url: str,
    ) -> KycVerification:
        """
        Create a new KYC submission.

        Multiple submissions are allowed (e.g. re-submission after rejection),
        but only one may be in 'pending' or 'verified' state at a time.
        """
        latest = await self._kyc.get_latest_for_user(user_id)
        if latest and latest.status in (
            VerificationStatus.pending,
            VerificationStatus.verified,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A KYC submission is already pending or verified. "
                    "You cannot submit another at this time."
                ),
            )

        record = await self._kyc.create(
            user_id=user_id,
            id_type=id_type,
            id_number=id_number,
            document_url=document_url,
            status=VerificationStatus.pending,
        )
        return record

    async def get_kyc_status(self, user_id: uuid.UUID) -> KycVerification:
        record = await self._kyc.get_latest_for_user(user_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No KYC submission found.",
            )
        return record
