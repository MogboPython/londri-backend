import httpx
import logging
import redis.asyncio as redis
from fastapi import Depends, HTTPException

from app import get_http_client, get_redis, logger
from datetime import datetime, timezone
from app.core.config import settings

REFRESH_THRESHOLD = 5 * 60
ACCESS_TOKEN_KEY = "nomba:access_token"
REFRESH_TOKEN_KEY = "nomba:refresh_token"

class PaymentService:
    def __init__(self, http_client: httpx.AsyncClient, redis_client: redis.Redis) -> None:
        super().__init__()
        self.http_client = http_client
        self.redis_client = redis_client
        self.base_url = settings.NOMBA_BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            # TODO: dynamic?
            "accountId": settings.NOMBA_ACCOUNT_ID,
        }
        self.client_id = settings.NOMBA_CLIENT_ID
        self.client_secret = settings.NOMBA_CLIENT_SECRET

    async def get_access_token(self) -> str:
        access_token, ttl, refresh_token = await self._read_cached()
        if access_token and ttl > REFRESH_THRESHOLD:
            return access_token

        return await self._refresh_or_issue(access_token, refresh_token)

    async def _refresh_or_issue(self, access_token: str, refresh_token: str) -> str:
        # XXX: for high traffic system should implement lock to prevent race condition in refreshes
        if access_token and refresh_token:
            token = await self._refresh_token(access_token, refresh_token)
            if token:
                return token
        return await self._issue_token()

    async def _read_cached(self) -> tuple[str | None, int, str | None]:
        async with self.redis_client.pipeline() as pipe:
            await pipe.get(ACCESS_TOKEN_KEY)
            await pipe.ttl(ACCESS_TOKEN_KEY)
            await pipe.get(REFRESH_TOKEN_KEY)
            access_token, ttl, refresh_token = await pipe.execute()
        return access_token, ttl, refresh_token

    async def _refresh_token(self, access_token: str, refresh_token: str) -> str | None:
        headers = {**self.headers, "Authorization": f"Bearer {access_token}"}
        try:
            response = await self.http_client.post(
                f"{self.base_url}/auth/token/refresh",
                headers=headers,
                json={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Nomba token refresh failed", exc_info=True)
            return None

        result = response.json()
        if result.get("code") != "00":
            logger.warning("Nomba refresh rejected: %s", result.get("description"))
            return None

        return await self._store_tokens(result["data"])

    async def _issue_token(self) -> str:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/auth/token/issue",
                headers=self.headers,
                json={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Nomba token issuance failed", exc_info=True)
            raise HTTPException(status_code=502, detail="Unable to authenticate with Nomba") from exc

        result = response.json()
        if result.get("code") != "00":
            raise HTTPException(status_code=502, detail="Nomba authentication rejected")

        return await self._store_tokens(result["data"])

    async def _store_tokens(self, data: dict) -> str:
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        ttl = self._ttl_from_expiry(data.get("expiresAt")) or settings.NOMBA_ACCESS_TOKEN_TTL

        # TODO: considering hashing with fernet, overkill?
        async with self.redis_client.pipeline() as pipe:
            await pipe.set(ACCESS_TOKEN_KEY, access_token, ex=ttl)
            await pipe.set(REFRESH_TOKEN_KEY, refresh_token)
            await pipe.execute()

        return access_token

    @staticmethod
    def _ttl_from_expiry(expires_at: str | None) -> int | None:
        if not expires_at:
            return None
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        seconds_left = (expiry - datetime.now(timezone.utc)).total_seconds()
        return max(int(seconds_left), 0) or None


def get_payment_service(
    http_client: httpx.AsyncClient = Depends(get_http_client),
    redis_client: redis.Redis = Depends(get_redis),
) -> PaymentService:
    return PaymentService(http_client, redis_client)