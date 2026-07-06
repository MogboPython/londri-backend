import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from twilio.rest import Client

from app import logger
from app.core.config import settings
from app.core.session import AsyncSessionFactory
from app.models.order import OrderStatus
from app.models.transaction import TransactionStatus
from app.repositories.order_repository import OrderRepository, OrderStatusEventRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.whatsapp import WhatsAppService

today = datetime.now(timezone.utc).strftime("%Y%m%d")

LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / f"payment_webhook_errors_{today}.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_payment_webhook_logger = logging.getLogger("webhook.amount_mismatch")
_payment_webhook_logger.setLevel(logging.ERROR)
if not _payment_webhook_logger.handlers:
    _handler = logging.FileHandler(LOG_PATH)
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    _payment_webhook_logger.addHandler(_handler)


def verify_nomba_signature(raw_body: bytes, headers: dict) -> bool:
    try:
        headers = {k.lower(): v for k, v in headers.items()}
        signature = headers.get("nomba-signature", "")
        computed_signature = hmac.new(
            settings.NOMBA_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(computed_signature, signature)
    except Exception:
        logger.error("Signature verification error", exc_info=True)
        return False


class WebhookService:
    def __init__(
            self,
            order_repo: OrderRepository,
            status_event_repo: OrderStatusEventRepository,
            txn_repo: TransactionRepository,
            whatsapp: WhatsAppService,
    ) -> None:
        self._order_repo = order_repo
        self._status_event_repo = status_event_repo
        self._txn_repo = txn_repo
        self._whatsapp = whatsapp

    async def process_webhook(self, body: dict[str, Any]) -> None:
        event_type = body.get("event_type")
        if event_type != "payment_success":
            logger.info("Ignoring webhook event: %s", event_type)
            return

        order = body.get("data", {}).get("order", {})
        await self._process_order_payment(order)

    async def _process_order_payment(self, order: dict[str, Any]) -> None:
        metadata = order.get("orderMetaData") or order.get("metadata") or {}
        transaction_reference_id = metadata.get("transaction_reference_id")
        order_reference = order.get("orderReference")
        webhook_amount = order.get("amount")

        if not transaction_reference_id:
            logger.error("Webhook missing transaction_reference_id in metadata: %s", order)
            return

        transaction = await self._txn_repo.get_by_reference_id(transaction_reference_id)
        if not transaction:
            logger.error("Webhook: no transaction found for reference_id %s", transaction_reference_id)
            return

        if transaction.status == TransactionStatus.success:
            logger.info("Transaction %s already marked as paid, skipping.", transaction_reference_id)
            return

        if webhook_amount is None or float(webhook_amount) != float(transaction.amount):
            _payment_webhook_logger.error(
                "Amount mismatch for transaction %s: webhook_amount=%s, recorded_amount=%s",
                transaction_reference_id, webhook_amount, transaction.amount,
            )
            return

        await self._txn_repo.update_instance(
            transaction,
            status=TransactionStatus.success,
            paid_at=datetime.now(timezone.utc),
        )

        if not order_reference:
            _payment_webhook_logger.error("Webhook missing orderReference for transaction %s", transaction_reference_id)
            return

        try:
            order_id = uuid.UUID(order_reference)
        except ValueError:
            _payment_webhook_logger.error("Webhook orderReference is not a valid UUID: %s", order_reference)
            return

        order_record = await self._order_repo.get_by_id(order_id)
        if not order_record:
            _payment_webhook_logger.error("Webhook: no order found for orderReference %s", order_reference)
            return

        from_status = order_record.status
        await self._order_repo.update_instance(order_record, status=OrderStatus.confirmed.value)
        await self._status_event_repo.create(
            order_id=order_record.id,
            from_status=from_status,
            to_status=OrderStatus.confirmed.value,
            actor_id=None,
            actor_role=None,
            note="Payment confirmed via Nomba webhook.",
        )

        customer_whatsapp = order.customer_whatsapp
        customer_name = order.customer_name.split(" ")[0]

        if customer_whatsapp:
            self._whatsapp.send_order_update_to_number(
                customer_name,
                customer_whatsapp,
                order_record.reference_id,
                OrderStatus.confirmed.value,
            )


async def run_webhook_processing(body: dict[str, Any]) -> None:
    async with AsyncSessionFactory() as session:
        svc = WebhookService(
            OrderRepository(session),
            OrderStatusEventRepository(session),
            TransactionRepository(session),
            WhatsAppService(Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)),
        )
        try:
            await svc.process_webhook(body)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.error("Webhook background processing failed", exc_info=True)
