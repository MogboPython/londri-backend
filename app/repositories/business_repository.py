import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[Business]):
    model = Business

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_owner(self, owner_user_id: uuid.UUID) -> Business | None:
        return await self.get_one_by(owner_user_id=owner_user_id)

    async def get_by_cac(self, cac_registration_number: str) -> Business | None:
        return await self.get_one_by(cac_registration_number=cac_registration_number)
