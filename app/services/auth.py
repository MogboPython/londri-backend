from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_password,
    verify_password,
)
from app.models.user import AuthMethod, User, UserRole
from app.repositories.user_repository import UserRepository
from .mail import send_email_async
from .whatsapp import WhatsAppService

OTP_PURPOSE_EMAIL_VERIFY = "email_verify"
OTP_PURPOSE_LOGIN = "login"
OTP_PURPOSE_PASSWORD_RESET = "password_reset"


class AuthService:
    def __init__(self, repo: UserRepository, whatsapp: WhatsAppService) -> None:
        self._repo = repo
        self._whatsapp = whatsapp

    async def register_owner(
        self,
        name: str,
        email: str,
        password: str,
        phone: str | None,
    ) -> dict:
        existing = await self._repo.get_by_email_or_phone(email, phone)
        if existing:
            errors = []
            if existing.email == email:
                errors.append("Email is already registered.")
            if existing.phone == phone:
                errors.append("Phone number is already registered.")

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"errors": errors}
            )

        user = await self._repo.create(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            phone=phone,
            role=UserRole.owner,
            auth_method=AuthMethod.password,
            is_email_verified=False,
        )

        otp_code = await self._issue_otp(
            user_id=user.id,
            purpose=OTP_PURPOSE_EMAIL_VERIFY
        )

        await send_email_async(
            subject="Verify your Account",
            email_to=user.email,
            body={"otp": otp_code},
            template="email.html",
        )

        # if user.phone:
        #     background_tasks.add_task(
        #         self._whatsapp.send_otp_to_number, user.phone, otp_code
        #     )

        return {"id": str(user.id), "email": user.email}

    async def verify_owner_email(self, email: str, otp_code: str) -> None:
        user = await self._get_user_or_404(email=email)
        if user.is_email_verified:
            return

        await self._consume_otp(user.id, otp_code, OTP_PURPOSE_EMAIL_VERIFY)
        await self._repo.update_email_verified(user.id)

    async def resend_email_verification(
        self, email: str
    ) -> None:
        user = await self._get_user_or_404(email=email)
        if user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified.",
            )
        otp_code = await self._issue_otp(user.id, OTP_PURPOSE_EMAIL_VERIFY)
        await send_email_async(
            subject="Verify your Account",
            email_to=email,
            body={"otp": otp_code},
            template="email.html",
        )

    async def login_owner(self, email: str, password: str) -> dict:
        user = await self._get_user_or_401(email=email)

        if not user.hashed_password or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )

        return {
            "access_token": create_access_token(str(user.id), user.role),
            "refresh_token": create_refresh_token(str(user.id), user.role),
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "is_email_verified": user.is_email_verified,
        }

    async def request_password_reset(
        self, email: str
    ) -> None:
        user = await self._repo.get_by_email(email)
        if not user:
            return
        otp_code = await self._issue_otp(user.id, OTP_PURPOSE_PASSWORD_RESET)
        await send_email_async(
            subject="Reset your password",
            email_to=email,
            body={"otp": otp_code},
            template="email.html",
        )

    async def reset_password(self, email: str, otp_code: str, new_password: str) -> None:
        user = await self._get_user_or_404(email=email)
        await self._consume_otp(user.id, otp_code, OTP_PURPOSE_PASSWORD_RESET)
        await self._repo.update_password(user.id, hash_password(new_password))

    async def get_profile(self, user: User) -> User:
        return await self._repo.get_with_bank_accounts(user.id)

    async def update_profile(
        self,
        user: User,
        name: str | None,
        email: str | None,
        phone: str | None,
        profile_picture_url: str | None,
        old_password: str | None,
        new_password: str | None,
    ) -> User:
        updates: dict = {}

        if name is not None:
            updates["name"] = name

        if profile_picture_url is not None:
            updates["profile_picture_url"] = profile_picture_url

        if email is not None and email.lower() != (user.email or "").lower():
            existing = await self._repo.get_by_email(email)
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email is already in use.",
                )
            updates["email"] = email.lower()

        if phone is not None and phone != user.phone:
            existing = await self._repo.get_by_phone(phone)
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number is already in use.",
                )
            updates["phone"] = phone

        if new_password is not None:
            if not user.hashed_password or not verify_password(old_password or "", user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Old password is incorrect.",
                )
            updates["hashed_password"] = hash_password(new_password)

        if updates:
            user = await self._repo.update_instance(user, **updates)

        return await self._repo.get_with_bank_accounts(user.id)

    async def request_customer_otp(
        self,
        name: str | None,
        email: str,
    ) -> None:
        user = await self._repo.get_by_email(email)

        if user is None:
            create_kwargs: dict = {
                "name": name or "Customer",
                "role": UserRole.customer,
                "auth_method": AuthMethod.otp,
                "email": email,
            }

            user = await self._repo.create(**create_kwargs)

        await self._check_otp_rate_limit(user.id, OTP_PURPOSE_LOGIN)

        otp_code = await self._issue_otp(user.id, OTP_PURPOSE_LOGIN)

        await send_email_async(
            subject="Your login code",
            email_to=user.email,
            body={"otp": otp_code},
            template="email.html",
        )

    async def verify_customer_otp(
        self,
        email: str,
        otp_code: str,
    ) -> dict:
        user = await self._repo.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found for the provided contact.",
            )

        is_new = not user.is_email_verified and user.auth_method == AuthMethod.otp

        await self._consume_otp(user.id, otp_code, OTP_PURPOSE_LOGIN)
        await self._repo.update_email_verified(user.id)

        return {
            "access_token": create_access_token(str(user.id), user.role),
            "refresh_token": create_refresh_token(str(user.id), user.role),
            "id": str(user.id),
            "role": user.role,
            "is_new_user": is_new,
        }

    async def refresh_tokens(self, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not a refresh token.",
            )

        user_id = payload.get("sub")
        role = payload.get("role")

        user = await self._repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated.",
            )

        return {
            "access_token": create_access_token(user_id, role),
            # "refresh_token": create_refresh_token(user_id, role),
        }

    async def _get_user_or_404(self, email: str):
        user = await self._repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    async def _get_user_or_401(self, email: str):
        user = await self._repo.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        return user

    async def _issue_otp(self, user_id, purpose: str) -> str:
        """Creates an OTP record and returns the plain-text code."""
        code = generate_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRE_MINUTES
        )
        await self._repo.create_otp(
            user_id=user_id,
            code_hash=hash_password(code),
            purpose=purpose,
            expires_at=expires_at,
        )
        return code

    async def _consume_otp(self, user_id, code: str, purpose: str) -> None:
        """Validates and marks the OTP as used. Raises HTTPException on failure."""
        otp = await self._repo.get_active_otp(user_id, purpose)
        if not otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid OTP found. Please request a new one.",
            )

        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please request a new OTP.",
            )

        if not verify_password(code, otp.code_hash):
            await self._repo.increment_otp_attempts(otp.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code.",
            )

        await self._repo.delete_otp(otp.id)

    async def _check_otp_rate_limit(self, user_id, purpose: str) -> None:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await self._repo.count_recent_otps(user_id, purpose, since)
        if count >= settings.OTP_RATE_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please try again later.",
            )
