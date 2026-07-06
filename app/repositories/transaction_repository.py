import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_reference_id(self, reference_id: str) -> Transaction | None:
        return await self.get_one_by(reference_id=reference_id)

    @staticmethod
    def _apply_filters(
        stmt: Select,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        reference_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Select:
        stmt = stmt.where(Transaction.business_id == business_id)
        if status:
            stmt = stmt.where(Transaction.status == status)
        if reference_id:
            stmt = stmt.where(Transaction.reference_id.ilike(f"%{reference_id}%"))
        if start_date:
            stmt = stmt.where(Transaction.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Transaction.created_at <= end_date)
        return stmt

    async def search(
        self,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        reference_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Transaction]:
        stmt = self._apply_filters(
            select(Transaction),
            business_id,
            status=status,
            reference_id=reference_id,
            start_date=start_date,
            end_date=end_date,
        )
        stmt = stmt.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_search(
        self,
        business_id: uuid.UUID,
        *,
        status: str | None = None,
        reference_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        stmt = self._apply_filters(
            select(func.count(Transaction.id)),
            business_id,
            status=status,
            reference_id=reference_id,
            start_date=start_date,
            end_date=end_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
