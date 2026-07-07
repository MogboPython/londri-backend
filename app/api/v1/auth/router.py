from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.auth.schemas import (
    BankAccountSummary,
    CustomerLoginResponse, CustomerOtpRequestRequest,
    CustomerOtpVerifyRequest, ForgotPasswordRequest,
    MessageResponse,
    OwnerLoginRequest,
    OwnerLoginResponse,
    OwnerRegisterRequest,
    OwnerRegisterResponse,
    RefreshTokenRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenPair,
    UpdateProfileRequest,
    UserMeResponse,
    VerifyEmailRequest,
)
from app.core.session import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth import AuthService
from app.services.whatsapp import WhatsAppService, get_whatsapp_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    whatsapp: WhatsAppService = Depends(get_whatsapp_service),
) -> AuthService:
    return AuthService(UserRepository(session), whatsapp)


@router.post(
    "/owner/register",
    response_model=OwnerRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a laundry owner account",
)
async def owner_register(
    body: OwnerRegisterRequest,
    svc: AuthService = Depends(get_auth_service),
):
    result = await svc.register_owner(
        name=body.name,
        email=str(body.email),
        password=body.password,
        phone=body.phone,
    )
    return OwnerRegisterResponse(
        **result,
        message="Registration successful. Please check your email for a verification code.",
    )


@router.post(
    "/owner/verify-email",
    response_model=MessageResponse,
    summary="Verify laundry owner email with OTP",
)
async def owner_verify_email(
    body: VerifyEmailRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await svc.verify_owner_email(email=str(body.email), otp_code=body.otp_code)
    return MessageResponse(message="Email verified successfully.")


@router.post(
    "/owner/resend-verification",
    response_model=MessageResponse,
    summary="Resend email verification OTP",
)
async def owner_resend_verification(
    body: ResendVerificationRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await svc.resend_email_verification(email=str(body.email))
    return MessageResponse(message="Verification code sent.")


@router.post(
    "/owner/login",
    response_model=OwnerLoginResponse,
    summary="Laundry owner login",
)
async def owner_login(
    body: OwnerLoginRequest,
    svc: AuthService = Depends(get_auth_service),
):
    result = await svc.login_owner(email=str(body.email), password=body.password)
    return OwnerLoginResponse(**result)


@router.post(
    "/owner/forgot-password",
    response_model=MessageResponse,
    summary="Request a password-reset OTP",
)
async def owner_forgot_password(
    body: ForgotPasswordRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await svc.request_password_reset(email=str(body.email))
    return MessageResponse(message="If an account exists, a reset code has been sent.")


@router.post(
    "/owner/reset-password",
    response_model=MessageResponse,
    summary="Reset password using OTP",
)
async def owner_reset_password(
    body: ResetPasswordRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await svc.reset_password(
        email=str(body.email),
        otp_code=body.otp_code,
        new_password=body.new_password,
    )
    return MessageResponse(message="Password reset successfully. Please log in.")

# TODO: logout and invalidate creds

@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh access token using a refresh token",
)
async def refresh_token(
    body: RefreshTokenRequest,
    svc: AuthService = Depends(get_auth_service),
):
    result = await svc.refresh_tokens(body.refresh_token)
    return TokenPair(**result)

@router.post(
    "/customer/request-otp",
    response_model=MessageResponse,
    summary="Request login/register OTP for customer",
)
async def customer_request_otp(
    body: CustomerOtpRequestRequest,
    svc: AuthService = Depends(get_auth_service),
):
    await svc.request_customer_otp(
        name=body.name,
        email=str(body.email),
    )
    return MessageResponse(message=f"OTP sent.")


@router.post(
    "/customer/verify-otp",
    response_model=CustomerLoginResponse,
    summary="Verify customer OTP and receive tokens",
)
async def customer_verify_otp(
    body: CustomerOtpVerifyRequest,
    svc: AuthService = Depends(get_auth_service),
):
    result = await svc.verify_customer_otp(
        # channel=body.channel,
        # phone=body.phone,
        email=str(body.email) if body.email else None,
        otp_code=body.otp_code,
    )
    return CustomerLoginResponse(**result)


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current authenticated user",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    user = await svc.get_profile(current_user)
    return _to_profile_response(user)


@router.patch(
    "/me",
    response_model=UserMeResponse,
    summary="Update the authenticated user's profile (including password change)",
)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    user = await svc.update_profile(
        current_user,
        name=body.name,
        email=str(body.email) if body.email else None,
        phone=body.phone,
        profile_picture_url=body.profile_picture_url,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    return _to_profile_response(user)


def _to_profile_response(user: User) -> UserMeResponse:
    return UserMeResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        profile_picture_url=user.profile_picture_url,
        is_email_verified=user.is_email_verified,
        bank_accounts=[
            BankAccountSummary(
                id=b.id,
                account_number=b.account_number,
                bank_code=b.bank_code,
                account_name=b.account_name,
                is_verified=b.is_verified,
                is_default=b.is_default,
            )
            for b in user.bank_accounts
        ],
    )
