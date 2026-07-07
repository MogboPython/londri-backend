from pydantic import BaseModel, EmailStr, Field, model_validator


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"

class MessageResponse(BaseModel):
    message: str


class OwnerRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{1,14}$")

class OwnerRegisterResponse(BaseModel):
    id: str
    email: str
    message: str

class OwnerLoginRequest(BaseModel):
    email: EmailStr
    password: str

class OwnerLoginResponse(TokenPair):
    id: str
    email: str
    role: str
    is_email_verified: bool

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


class CustomerOtpRequestRequest(BaseModel):
    """Customer requests an OTP to log in or register."""
    name: str | None = Field(default=None, max_length=255)
    email: EmailStr # | None = None


class CustomerOtpVerifyRequest(BaseModel):
    """Customer submits the OTP to receive auth tokens."""
    email: EmailStr # | None = None
    otp_code: str = Field(..., min_length=6, max_length=6)


class CustomerLoginResponse(TokenPair):
    id: str
    role: str
    is_new_user: bool

class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, description="Optional refresh token to also blacklist.")


class LogoutResponse(BaseModel):
    message: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class BankAccountSummary(BaseModel):
    id: int
    account_number: str
    bank_code: str
    account_name: str
    is_verified: bool
    is_default: bool


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{1,14}$")
    profile_picture_url: str | None = None
    old_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)
    confirm_password: str | None = None

    @model_validator(mode="after")
    def validate_password_change(self) -> "UpdateProfileRequest":
        if self.old_password or self.new_password or self.confirm_password:
            if not (self.old_password and self.new_password):
                raise ValueError(
                    "old_password and new_password are all required to change your password."
                )
        return self


class UserMeResponse(BaseModel):
    id: str
    name: str
    email: str | None
    phone: str | None
    role: str
    profile_picture_url: str | None = None
    is_email_verified: bool
    bank_accounts: list[BankAccountSummary] = Field(default_factory=list)
