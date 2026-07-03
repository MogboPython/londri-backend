from pydantic import BaseModel, Field


class BankResponse(BaseModel):
    code: str
    name: str


class AccountNameResponse(BaseModel):
    account_name: str
    account_number: str
    bank_code: str


class BankAccountRequest(BaseModel):
    account_number: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    bank_code: str = Field(..., min_length=2, max_length=20)


class BankAccountResponse(BaseModel):
    id: int
    account_number: str
    bank_code: str
    account_name: str
    is_default: bool
