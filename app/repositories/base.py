from typing import Any, Generic, TypeVar

from sqlalchemy import select, update as sa_update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]  # subclasses must set this class attribute

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, record_id: Any) -> ModelT | None:
        result = await self._session.execute(
            select(self.model).where(self.model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self._session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_one_by(self, **filters: Any) -> ModelT | None:
        """Return the first row matching all keyword filters."""
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many_by(
        self, *, limit: int = 100, offset: int = 0, **filters: Any
    ) -> list[ModelT]:
        """Return all rows matching all keyword filters."""
        stmt = select(self.model).limit(limit).offset(offset)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> ModelT:
        """Insert a new row and return it with DB-generated fields populated."""
        instance = self.model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update_by_id(self, record_id: Any, **values: Any) -> None:
        """Bulk-UPDATE a row by primary key without loading it into memory."""
        await self._session.execute(
            sa_update(self.model)
            .where(self.model.id == record_id)
            .values(**values)
        )

    async def update_instance(self, instance: ModelT, **values: Any) -> ModelT:
        """Update an already-loaded ORM instance and flush."""
        for field, value in values.items():
            setattr(instance, field, value)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete_by_id(self, record_id: Any) -> None:
        await self._session.execute(
            sa_delete(self.model).where(self.model.id == record_id)
        )

    async def delete_instance(self, instance: ModelT) -> None:
        await self._session.delete(instance)
        await self._session.flush()
