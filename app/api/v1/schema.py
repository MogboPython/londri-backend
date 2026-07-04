from typing import Any

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    data: Any
    message: str | None = None
    code: int

