import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import httpx
import redis.asyncio as redis
from fastapi import Depends, HTTPException

from app import get_http_client, get_redis, logger
from app.core.config import settings
from .dependencies import bank_code_exists, ttl_from_expiry

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
        self.account_id = settings.NOMBA_ACCOUNT_ID
        self.headers = {
            "Content-Type": "application/json",
            # TODO: dynamic? Subaccount
            "accountId": self.account_id,
        }
        self.client_id = settings.NOMBA_CLIENT_ID
        self.client_secret = settings.NOMBA_CLIENT_SECRET
        self.callback_url = f"{settings.FRONTEND_URL}/payment/return"

    # TODO: move to nomba request
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
            payload: Any | None = None,
            headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=headers,
                params=params,
                json=payload,
                timeout=30,
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
            '/v1/auth/token/refresh',
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
            '/v1/auth/token/issue',
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

    # XXX: not implementing since we can't create subaccounts for this hackathon
    async def generate_subaccount(self, business_name: str, account_ref: str) -> Any:
        headers = await self._get_headers()
        payload = {
            "accountName": business_name,
            "accountRef": account_ref
        }

        result = await self._make_nomba_request(
            'POST',
            '/v1/accounts/sub-accounts',
            payload=payload,
            headers=headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        return result["data"]

    async def get_virtual_account(self, sub_account_id: str, business_id: str, business_name: str) -> str:
        headers = await self._get_headers()

        payload = {
            "accountRef": business_id,
            "accountName": business_name,
        }

        result = await self._make_nomba_request(
            'POST',
            f'/v1/accounts/virtual/{sub_account_id}',
            payload=payload,
            headers=headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        return result["data"]

    async def get_bank_codes(self) -> List[dict[str, str]]:
        bank_codes = await self.redis_client.get(BANK_CODES)
        if bank_codes:
            bank_codes = json.loads(bank_codes)
            return bank_codes

        headers = await self._get_headers()

        result = await self._make_nomba_request(
            'GET',
            '/v1/transfers/banks',
            headers=headers,
        )

        self._fmt_nomba_resp_code(result.get("code"))

        bank_codes = result["data"]
        await self.redis_client.set(BANK_CODES, json.dumps(bank_codes))

        return bank_codes

    # XXX: I am sending the account name to the frontend, then saving after they confirm,
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
            '/v1/transfers/bank/lookup',
            headers=headers,
            payload=payload,
        )

        self._fmt_nomba_resp_code(result.get("code"))
        account_name = result["data"]["accountName"]
        await self.redis_client.set(ACCOUNT_NAME, account_name, ex=300)

        return account_name

    @staticmethod
    def _split_97_3(subaccount_id: str, service_account_id: str) -> dict:
        """
        97% of the charge settles to `subaccount_id`, the remaining 3% (your
        service/platform fee) settles to `account_id`.
        """
        return {
            "splitType": "PERCENTAGE",
            "splitList": [
                {"accountId": subaccount_id, "value": "97"},
                {"accountId": service_account_id, "value": "3"},
            ],
        }

    async def create_charge(
            self,
            amount: int,
            customer_email: str,
            subaccount_id: str,
            order_reference: Optional[str] = None,
            customer_id: Optional[str] = None,
            tokenize_card: bool = False,
            currency: str = "NGN",
            metadata: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        headers = await self._get_headers()

        order_reference = order_reference or str(uuid.uuid4())
        order: dict[str, Any] = {
            "orderReference": order_reference,
            "customerEmail": customer_email,
            "callbackUrl": self.callback_url,
            "amount": amount* 100,
            "currency": currency,
            "splitRequest": self._split_97_3(subaccount_id, self.account_id),
        }

        if customer_id:
            order["customerId"] = customer_id
        if tokenize_card:
            order["allowedPaymentMethods"] = ["Card"]
        else:
            order["allowedPaymentMethods"] = ["Card", "Transfer", "USSD"]
        if metadata:
            order["orderMetaData"] = metadata

        payload = {"order": order, "tokenizeCard": tokenize_card}

        result = await self._make_nomba_request(
            'POST',
            '/v1/checkout/order',
            headers=headers,
            payload=payload,
        )

        return {
            "order_reference": order_reference,
            "checkout_link": result["data"]["checkoutLink"],
        }

    async def charge_tokenized_card(
            self,
            token_key: str,
            amount: int,
            customer_email: str,
            subaccount_id: str,
            customer_id: Optional[str] = None,
            currency: str = "NGN",
            order_reference: Optional[str] = None,
            metadata: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        headers = await self._get_headers()

        order_reference = order_reference or str(uuid.uuid4())
        order: dict[str, Any] = {
            "orderReference": order_reference,
            "customerEmail": customer_email,
            "callbackUrl": self.callback_url,
            "amount": amount * 100,
            "currency": currency,
            "splitRequest": self._split_97_3(subaccount_id, self.account_id),
        }
        if customer_id:
            order["customerId"] = customer_id
        if metadata:
            order["orderMetaData"] = metadata

        payload = {"order": order, "tokenKey": token_key},

        result = await self._make_nomba_request(
            'POST',
            '/v1/checkout/tokenized-card-payment',
            headers=headers,
            payload=payload,
        )

        return {"order_reference": order_reference, "data": result["data"]}

    async def delete_tokenized_card(self, token_key: str) -> dict[str, Any]:
       # TODO: update the caller's DB row (`is_active = False`)
        headers = await self._get_headers()

        result = await self._make_nomba_request(
            'POST',
            '/v1/checkout/tokenized-card-data',
            headers=headers,
            payload={"tokenKey": token_key},
        )

        return result["data"]

    @staticmethod
    def get_available_balance():
        return 100000

    # def transfer_to_bank_account(
    #         self,
    #         *,
    #         subaccount_id: str,
    #         account_number: str,
    #         account_name: str,
    #         bank_code: str,
    #         amount: int,
    #         sender_name: Optional[str] = None,
    #         narration: Optional[str] = None,
    #         merchant_tx_ref: Optional[str] = None,
    # ) -> dict[str, Any]:
    #     """
    #     Pay out from a sub-account's wallet straight to an external Nigerian
    #     bank account (NIP transfer).
    #
    #     Requires Nomba to have profiled/enabled the sub-account for bank
    #     transfers first - this isn't self-service, reach out to Nomba to turn
    #     it on.
    #
    #     `merchant_tx_ref` is the documented idempotency key - generate a
    #     fresh one per logical payout and only reuse it when retrying that
    #     exact same payout.
    #
    #     A 200 response means it settled synchronously (`data.status ==
    #     "SUCCESS"`). A 201 means `PENDING_BILLING` - the docs are explicit
    #     here: mark it pending and do NOT retry with a new reference, just
    #     wait for the `payout_success` / `payout_failed` webhook.
    #     """
    #     merchant_tx_ref = merchant_tx_ref or str(uuid.uuid4())
    #     body: dict[str, Any] = {
    #         "amount": amount * 100,
    #         "accountNumber": account_number,
    #         "accountName": account_name,
    #         "bankCode": bank_code,
    #         "merchantTxRef": merchant_tx_ref,
    #     }
    #     if sender_name:
    #         body["senderName"] = sender_name
    #     if narration:
    #         body["narration"] = narration
    #
    #     url = f"{self._config.base_url}/v2/transfers/bank/{subaccount_id}"
    #     resp = self._session.post(
    #         url,
    #         headers=self._headers(idempotency_key=merchant_tx_ref),
    #         json=body,
    #         timeout=30,
    #     )
    #     payload = self._parse(resp)
    #     return {
    #         "merchant_tx_ref": merchant_tx_ref,
    #         "data": payload.get("data", {}),
    #         "http_status": resp.status_code,
    #     }
    #

def get_payment_service(
    http_client: httpx.AsyncClient = Depends(get_http_client),
    redis_client: redis.Redis = Depends(get_redis),
) -> PaymentService:
    return PaymentService(http_client, redis_client)