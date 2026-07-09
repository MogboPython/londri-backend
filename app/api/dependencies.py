import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app import get_redis
from app.core.security import decode_token, is_jti_blacklisted
from app.models.user import User, UserRole
from app.core.session import get_db_session
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
    request: Request = None,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    # Check if the token's JTI has been blacklisted (logout / revoke)
    jti = payload.get("jti")
    if jti and request is not None:
        redis_client = get_redis(request)
        if await is_jti_blacklisted(jti, redis_client):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked.",
            )

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Laundry owner access required.",
        )
    return current_user


async def require_customer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.customer, UserRole.owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required.",
        )
    return current_user
