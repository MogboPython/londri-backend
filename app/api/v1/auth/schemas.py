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
    channel: str = Field(..., pattern="^(whatsapp|email)$")
    # Exactly one of whatsapp_number or email required depending on channel
    whatsapp_number: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_channel_fields(self) -> "CustomerOtpRequestRequest":
        if self.channel == "whatsapp" and not self.whatsapp_number:
            raise ValueError("whatsapp_number is required when channel is 'whatsapp'")
        if self.channel == "email" and not self.email:
            raise ValueError("email is required when channel is 'email'")
        return self


class CustomerOtpVerifyRequest(BaseModel):
    """Customer submits the OTP to receive auth tokens."""

    channel: str = Field(..., pattern="^(whatsapp|email)$")
    whatsapp_number: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    otp_code: str = Field(..., min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_channel_fields(self) -> "CustomerOtpVerifyRequest":
        if self.channel == "whatsapp" and not self.whatsapp_number:
            raise ValueError("whatsapp_number is required when channel is 'whatsapp'")
        if self.channel == "email" and not self.email:
            raise ValueError("email is required when channel is 'email'")
        return self


class CustomerLoginResponse(TokenPair):
    id: str
    role: str
    is_new_user: bool

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserMeResponse(BaseModel):
    id: str
    name: str
    email: str | None
    phone: str | None
    role: str
    is_email_verified: bool
