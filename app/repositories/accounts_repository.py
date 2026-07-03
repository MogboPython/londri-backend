import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import BankAccount
from app.repositories.base import BaseRepository


class BankAccountRepository(BaseRepository[BankAccount]):
    model = BankAccount

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_user(self, user_id: uuid.UUID) -> list[BankAccount]:
        return await self.get_many_by(user_id=user_id)

    async def get_by_user_and_account(
        self, user_id: uuid.UUID, account_number: str, bank_code: str
    ) -> BankAccount | None:
        """Used to enforce the unique constraint before hitting the DB."""
        results = await self.get_many_by(user_id=user_id, account_number=account_number, bank_code=bank_code)
        return results[0] if results else None
