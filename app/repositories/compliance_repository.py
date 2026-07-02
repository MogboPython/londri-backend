import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import KybVerification, KycVerification
from app.repositories.base import BaseRepository


class KycRepository(BaseRepository[KycVerification]):
    model = KycVerification

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_latest_for_user(self, user_id: uuid.UUID) -> KycVerification | None:
        """Return the most recently created KYC record for a user."""
        records = await self.get_many_by(user_id=user_id)
        if not records:
            return None
        return max(records, key=lambda r: r.created_at)


class KybRepository(BaseRepository[KybVerification]):
    model = KybVerification

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_latest_for_business(
        self, business_id: uuid.UUID
    ) -> KybVerification | None:
        records = await self.get_many_by(business_id=business_id)
        if not records:
            return None
        return max(records, key=lambda r: r.created_at)
