import uuid

from fastapi import HTTPException, status

from app.models.compliance import KybVerification, KycVerification, VerificationStatus
from app.repositories.business_repository import BusinessRepository
from app.repositories.compliance_repository import KybRepository, KycRepository


class ComplianceService:
    def __init__(
        self,
        kyc_repo: KycRepository,
        kyb_repo: KybRepository,
        business_repo: BusinessRepository,
    ) -> None:
        self._kyc = kyc_repo
        self._kyb = kyb_repo
        self._business_repo = business_repo

    async def _resolve_business(self, owner_id: uuid.UUID) -> uuid.UUID:
        business = await self._business_repo.get_by_owner(owner_id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No business registered for this account.",
            )
        return business.id

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

        id_number_taken = await self._kyc.get_one_by(id_number=id_number)
        if id_number_taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A KYC submission with this ID already exists.",
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

    async def submit_kyb(
        self,
        owner_id: uuid.UUID,
        proof_of_address: str,
        cac_registration_number: str,
        business_premises_photos: list[str],
    ) -> KybVerification:
        business_id = await self._resolve_business(owner_id)

        latest = await self._kyc.get_latest_for_user(business_id)
        if latest and latest.status in (
            VerificationStatus.pending,
            VerificationStatus.verified,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A KYB submission is already pending or verified. "
                    "You cannot submit another at this time."
                ),
            )

        cac_taken = await self._kyb.get_one_by(cac_registration_number=cac_registration_number)
        if cac_taken:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A business with this CAC registration number already exists.",
            )

        record = await self._kyb.create(
            business_id=business_id,
            proof_of_address=proof_of_address,
            cac_registration_number=cac_registration_number,
            business_premises_photos=business_premises_photos,
            status=VerificationStatus.pending,
        )
        return record

    async def get_kyb_status(self, owner_id: uuid.UUID) -> KybVerification:
        business_id = await self._resolve_business(owner_id)

        record = await self._kyb.get_latest_for_business(business_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No KYB submission found.",
            )
        return record
