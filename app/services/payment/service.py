import json
from datetime import datetime, timedelta, timezone
from typing import Any, List

import httpx
import redis.asyncio as redis
from fastapi import Depends, HTTPException

from app import get_http_client, get_redis, logger
from app.core.config import settings
from .dependencies import ttl_from_expiry, bank_code_exists

REFRESH_THRESHOLD = 5 * 60
ACCESS_TOKEN_KEY = "nomba:access_token"
REFRESH_TOKEN_KEY = "nomba:refresh_token"
BANK_CODES = "nomba:bank_codes"

class PaymentService:
    def __init__(self, http_client: httpx.AsyncClient, redis_client: redis.Redis) -> None:
        super().__init__()
        self.http_client = http_client
        self.redis_client = redis_client
        self.base_url = settings.NOMBA_BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            # TODO: dynamic? Subaccount
            "accountId": settings.NOMBA_ACCOUNT_ID,
        }
        self.client_id = settings.NOMBA_CLIENT_ID
        self.client_secret = settings.NOMBA_CLIENT_SECRET

    @staticmethod
    def _fmt_nomba_resp_code(code: str) -> None:
        if code == "00":
            return

        match code:
            case "400":
                raise HTTPException(status_code=400, detail="Request to Nomba failed")
            case "401":
                raise HTTPException(status_code=401, detail="Unauthorized request to Nomba")
            case "403":
                raise HTTPException(status_code=403, detail="Forbidden request to Nomba")
            case "404":
                raise HTTPException(status_code=404, detail="Record not found")
            case "429":
                raise HTTPException(status_code=429, detail="Too many request to Nomba")
            case _:
                raise HTTPException(status_code=500, detail="Server Error")

    async def _get_headers(self):
        token = await self._get_access_token()
        headers = {**self.headers, "Authorization": f"Bearer {token}"}

        return headers

    async def _make_nomba_request(
            self,
            method: str,
            endpoint: str,
            params: dict[str, Any] | None = None,
            payload: dict[str, Any] | None = None,
            headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to make Nomba request", exc_info=True)
            raise HTTPException(status_code=502, detail="Bad Gateway") from exc

        return response.json()

    async def _get_access_token(self) -> str:
        access_token, ttl, refresh_token = await self._read_cached()
        if access_token and ttl > REFRESH_THRESHOLD:
            return access_token

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
        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}

        result = await self._make_nomba_request(
            'POST',
            '/auth/token/refresh',
            payload=payload,
            headers=headers,
        )

        if result.get("code") != "00":
            logger.warning("Nomba refresh rejected: %s", result.get("description"))
            return None

        return await self._store_tokens(result["data"])

    async def _issue_token(self) -> str:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        result = await self._make_nomba_request(
            'POST',
            '/auth/token/issue',
            payload=payload,
            headers=self.headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        return await self._store_tokens(result["data"])

    async def _store_tokens(self, data: dict) -> str:
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        ttl = ttl_from_expiry(data.get("expiresAt")) or settings.NOMBA_ACCESS_TOKEN_TTL

        async with self.redis_client.pipeline() as pipe:
            await pipe.set(ACCESS_TOKEN_KEY, access_token, ex=ttl)
            await pipe.set(REFRESH_TOKEN_KEY, refresh_token)
            await pipe.execute()

        return access_token

    # TODO: account name pattern Laundry - Business Name
    # TODO: accountRef pattern londri_business_date_joined
    # TODO: verify return
    # TODO: check list of subaccounts
    async def generate_subaccount(self, business_name: str, account_ref: str) -> Any:
        headers = await self._get_headers()
        payload = {
            "accountName": business_name,
            "accountRef": account_ref
        }

        result = await self._make_nomba_request(
            'POST',
            '/accounts/sub-accounts',
            payload=payload,
            headers=headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        return result["data"]

    async def get_virtual_account(self, sub_account_id: str, business_name: str, account_ref: str) -> str:
        headers = await self._get_headers()
        now = datetime.now(timezone.utc)
        # XXX: how long the virtual account should last for now
        next_one_year = now + timedelta(days=365)
        next_one_year_fmt = next_one_year.strftime("%Y-%m-%d %H:%M:%S")

        payload = {
            "accountRef": account_ref,
            "accountName": business_name,
            "expiryDate": next_one_year_fmt,
        }

        result = await self._make_nomba_request(
            'POST',
            f'/accounts/virtual/{sub_account_id}',
            payload=payload,
            headers=headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        return result["data"]

    # async def create_payment(self, amount: int, business_name: str, account_ref: str):
    #     headers = await self._get_headers()
    #
    #     return "paid"

    async def get_bank_codes(self) -> List[dict[str, str]]:
        bank_codes = await self.redis_client.get(BANK_CODES)
        if bank_codes:
            bank_codes = json.loads(bank_codes)
            return bank_codes

        headers = await self._get_headers()

        result = await self._make_nomba_request(
            'GET',
            '/transfers/banks',
            headers=headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))

        bank_codes = result["data"]
        await self.redis_client.set(BANK_CODES, json.dumps(bank_codes))

        return bank_codes

    # TODO: I am sending the account name to the frontend, then saving after they confirm,
    #  worried it can be changed so might revert to querying the name twice
    async def get_customer_acc_name(self, account_number: str, bank_code: str) -> str:
        ACCOUNT_NAME = f"account_name_{account_number}_{bank_code}"
        account_name = await self.redis_client.get(ACCOUNT_NAME)
        if account_name:
            return account_name

        bank_codes_list = await self.get_bank_codes()

        if not bank_code_exists(bank_code, bank_codes_list):
            raise HTTPException(status_code=404, detail="Bank not found")

        headers = await self._get_headers()
        payload = {
            "accountNumber": account_number,
            "bankCode": bank_code
        }

        result = await self._make_nomba_request(
            'POST',
            '/transfers/bank/lookup',
            headers=headers,
            payload=payload,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        account_name = result["data"]["accountName"]
        await self.redis_client.set(ACCOUNT_NAME, account_name, ex=300)

        return account_name


def get_payment_service(
    http_client: httpx.AsyncClient = Depends(get_http_client),
    redis_client: redis.Redis = Depends(get_redis),
) -> PaymentService:
    return PaymentService(http_client, redis_client)