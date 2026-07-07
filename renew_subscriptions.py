#!/usr/bin/env python3

import logging
import os
import random
import string
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.accounts import BusinessSubaccount, TokenizedCard
from app.models.catalog import SubscriptionPlan
from app.models.subscription import CustomerSubscription, SubscriptionStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User

NOMBA_BASE_URL = os.environ.get("NOMBA_BASE_URL", "https://sandbox.nomba.com")
NOMBA_CLIENT_ID = os.environ["NOMBA_CLIENT_ID"]
NOMBA_CLIENT_SECRET = os.environ["NOMBA_CLIENT_SECRET"]
NOMBA_ACCOUNT_ID = os.environ["NOMBA_ACCOUNT_ID"]
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
DATABASE_URL = os.environ["DATABASE_SYNC_URL"]

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

RUN_DATE_STR = datetime.now(timezone.utc).strftime("%Y%m%d")
LOG_FILE = LOGS_DIR / f"subscription_renewals_{RUN_DATE_STR}.log"

logger = logging.getLogger("subscription_renewal")
logger.setLevel(logging.INFO)

_file_handler = logging.FileHandler(LOG_FILE)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_console_handler)


def get_access_token() -> str:
    url = f"{NOMBA_BASE_URL}/v1/auth/token/issue"
    payload = {
        "grant_type": "client_credentials",
        "client_id": NOMBA_CLIENT_ID,
        "client_secret": NOMBA_CLIENT_SECRET,
    }
    headers = {
        "accountId": NOMBA_ACCOUNT_ID,
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    body = response.json()

    if body.get("code") != "00":
        raise RuntimeError(f"Failed to issue Nomba access token: {body}")

    return body["data"]["access_token"]


def charge_tokenized_card(
    token: str,
    *,
    token_key: str,
    amount: int,
    customer_email: str,
    subaccount_id: str,
    order_reference: str,
    metadata: dict[str, str],
) -> dict:
    url = f"{NOMBA_BASE_URL}/v1/checkout/tokenized-card-payment"
    headers = {
        "accountId": NOMBA_ACCOUNT_ID,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    order = {
        "orderReference": order_reference,
        "customerEmail": customer_email,
        "callbackUrl": f"{FRONTEND_URL}/orders",
        "amount": amount * 100,
        "currency": "NGN",
        "accountId": subaccount_id,
        "orderMetaData": metadata,
    }
    payload = {"order": order, "tokenKey": token_key}

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    body = response.json()

    if body.get("code") != "00":
        raise RuntimeError(f"Failed to charge tokenized card: {body}")

    return body["data"]


def generate_transaction_reference(session: Session) -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    while True:
        letters = "".join(random.choices(string.ascii_uppercase, k=3))
        digits = f"{random.randint(0, 999):03d}"
        candidate = f"PAY-{today_str}-{letters}{digits}"
        existing = session.execute(
            select(Transaction.id).where(Transaction.reference_id == candidate)
        ).scalar_one_or_none()
        if not existing:
            return candidate


def get_due_subscriptions(session: Session) -> list[CustomerSubscription]:
    """Active subscriptions whose billing date has arrived (or passed)."""
    now = datetime.now(timezone.utc)
    stmt = select(CustomerSubscription).where(
        CustomerSubscription.status == SubscriptionStatus.active,
        CustomerSubscription.next_billing_date.isnot(None),
        CustomerSubscription.next_billing_date <= now,
    )
    return list(session.scalars(stmt).all())


def get_active_tokenized_card(session: Session, user_id: uuid.UUID) -> TokenizedCard | None:
    stmt = (
        select(TokenizedCard)
        .where(TokenizedCard.user_id == user_id, TokenizedCard.is_active == True)  # noqa: E712
        .order_by(TokenizedCard.created_at.desc())
    )
    return session.scalars(stmt).first()


def get_business_subaccount(session: Session, business_id: uuid.UUID) -> BusinessSubaccount | None:
    return session.scalars(
        select(BusinessSubaccount).where(BusinessSubaccount.business_id == business_id)
    ).first()


def renew_subscription(session: Session, token: str, subscription: CustomerSubscription) -> None:
    plan = session.get(SubscriptionPlan, subscription.plan_id)
    if not plan:
        logger.error("No plan found for subscription %s, skipping.", subscription.id)
        return

    customer = session.get(User, subscription.customer_id)
    if not customer or not customer.email:
        logger.error("No customer/email found for subscription %s, skipping.", subscription.id)
        return

    tokenized_card = get_active_tokenized_card(session, subscription.customer_id)
    if not tokenized_card:
        logger.error(
            "No saved card on file for customer %s (subscription %s) — cannot renew.",
            subscription.customer_id, subscription.id,
        )
        return

    subaccount = get_business_subaccount(session, subscription.business_id)
    if not subaccount:
        logger.error(
            "No subaccount found for business %s — skipping subscription %s.",
            subscription.business_id, subscription.id,
        )
        return

    reference_id = generate_transaction_reference(session)
    order_reference = str(uuid.uuid4())

    transaction = Transaction(
        business_id=subscription.business_id,
        subscription_id=subscription.id,
        reference_id=reference_id,
        merchant_tx_ref=order_reference,
        amount=plan.price,
        currency="NGN",
        status=TransactionStatus.pending,
    )
    session.add(transaction)
    session.flush()

    # Marked past_due immediately, before the charge outcome is known — the
    # webhook flips this back to `active` on success or `inactive` on failure.
    subscription.status = SubscriptionStatus.past_due

    metadata = {
        "subscription_id": str(subscription.id),
        "transaction_reference_id": transaction.reference_id,
        "operation": "subscription-renewal",
        "plan_id": str(plan.id),
        "customer_id": str(customer.id),
    }

    try:
        charge_tokenized_card(
            token,
            token_key=tokenized_card.token_key,
            amount=int(plan.price),
            customer_email=customer.email,
            subaccount_id=subaccount.provider_subaccount_id,
            order_reference=order_reference,
            metadata=metadata,
        )
        logger.info(
            "Renewal charge initiated for subscription %s (transaction %s, order_reference %s).",
            subscription.id, transaction.reference_id, order_reference,
        )
    except Exception:
        # Left as past_due with a pending transaction — resolved later by the
        # payment webhook, or picked up again by a future run/reconciliation.
        logger.exception(
            "Failed to initiate renewal charge for subscription %s (transaction %s).",
            subscription.id, transaction.reference_id,
        )

    session.commit()


def main() -> None:
    logger.info("Starting subscription renewal run at %s", datetime.now(timezone.utc).isoformat())

    try:
        token = get_access_token()
    except Exception:
        logger.exception("Failed to obtain Nomba access token")
        sys.exit(1)

    engine = create_engine(DATABASE_URL)
    SessionFactory = sessionmaker(bind=engine)

    with SessionFactory() as session:
        due_subscriptions = get_due_subscriptions(session)
        logger.info("Found %d subscription(s) due for renewal.", len(due_subscriptions))

        for subscription in due_subscriptions:
            try:
                renew_subscription(session, token, subscription)
            except Exception:
                session.rollback()
                logger.exception("Unexpected error renewing subscription %s", subscription.id)

    logger.info("Subscription renewal run complete. Log written to %s", LOG_FILE)


if __name__ == "__main__":
    main()
