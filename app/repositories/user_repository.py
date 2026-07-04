import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OtpRecord, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_email(self, email: str) -> User | None:
        return await self.get_one_by(email=email.lower())

    async def get_by_phone(self, phone: str) -> User | None:
        return await self.get_one_by(phone=phone)

    async def get_by_email_or_phone(
        self, email: str | None, phone: str | None
    ) -> User | None:
        result = await self._session.execute(
            select(self.model).where(
                or_(
                    self.model.email == email,
                    self.model.phone == phone
                )
            )
        )

        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> User:
        if kwargs.get("email"):
            kwargs["email"] = kwargs["email"].lower()
        if kwargs.get("phone"):
            kwargs["phone"] = kwargs["phone"].replace(" ", "")
        return await super().create(**kwargs)

    async def update_email_verified(self, user_id: uuid.UUID) -> None:
        await self.update_by_id(user_id, is_email_verified=True)

    async def update_password(self, user_id: uuid.UUID, hashed_password: str) -> None:
        await self.update_by_id(user_id, hashed_password=hashed_password)

    async def create_otp(self, **kwargs) -> OtpRecord:
        otp = OtpRecord(**kwargs)
        self._session.add(otp)
        await self._session.flush()
        return otp

    async def get_active_otp(
        self, user_id: uuid.UUID, purpose: str
    ) -> OtpRecord | None:
        """Returns the most recent unused, unexpired OTP for a user + purpose."""
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(OtpRecord)
            .where(
                OtpRecord.user_id == user_id,
                OtpRecord.purpose == purpose,
                OtpRecord.is_used == False,  # noqa: E712
                OtpRecord.expires_at > now,
            )
            .order_by(OtpRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_recent_otps(
        self, user_id: uuid.UUID, purpose: str, since: datetime
    ) -> int:
        """Count OTP requests for rate limiting."""
        result = await self._session.execute(
            select(OtpRecord).where(
                OtpRecord.user_id == user_id,
                OtpRecord.purpose == purpose,
                OtpRecord.created_at >= since,
            )
        )
        return len(result.scalars().all())

    async def delete_otp(self, otp_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(OtpRecord).where(OtpRecord.id == otp_id)
        )

    async def increment_otp_attempts(self, otp_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(OtpRecord).where(OtpRecord.id == otp_id)
        )
        otp = result.scalar_one_or_none()
        if otp:
            otp.attempts += 1
            await self._session.flush()
