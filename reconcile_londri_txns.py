#!/usr/bin/env python3

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


try:
    from app.models.transaction import Transaction
except ImportError:
    Transaction = None

NOMBA_BASE_URL = os.environ.get("NOMBA_BASE_URL", "https://sandbox.nomba.com")
NOMBA_CLIENT_ID = os.environ["NOMBA_CLIENT_ID"]
NOMBA_CLIENT_SECRET = os.environ["NOMBA_CLIENT_SECRET"]
NOMBA_ACCOUNT_ID = os.environ["NOMBA_ACCOUNT_ID"]
NOMBA_SUB_ACCOUNT_ID = os.environ["NOMBA_SUB_ACCOUNT_ID"]
DATABASE_URL = os.environ["DATABASE_SYNC_URL"]

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

RUN_DATE_STR = datetime.now(timezone.utc).strftime("%Y%m%d")
LOG_FILE = LOGS_DIR / f"missing_transactions_{RUN_DATE_STR}.log"

logger = logging.getLogger("nomba_reconciliation")
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


def fetch_transactions(token: str, date_from: str, date_to: str, status: str = "success") -> list[dict]:
    url = f"{NOMBA_BASE_URL}/v1/transactions/accounts/{NOMBA_SUB_ACCOUNT_ID}"
    headers = {
        "accountId": NOMBA_ACCOUNT_ID,
        "Authorization": f"Bearer {token}",
    }

    all_results: list[dict] = []
    cursor: str | None = None

    while True:
        params = {"dateFrom": date_from, "dateTo": date_to, "status": status}
        if cursor:
            params["cursor"] = cursor

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        body = response.json()

        if body.get("code") != "00":
            raise RuntimeError(f"Failed to fetch transactions: {body}")

        data = body.get("data", {})
        results = data.get("results", [])
        all_results.extend(results)

        cursor = data.get("cursor")
        if not cursor or not results:
            break

    return all_results

def find_missing_refs(all_refs: list[str]) -> list[str]:
    if Transaction is None:
        raise ImportError("Could not import Transaction model.")

    if not all_refs:
        return []

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        found_refs = set(
            session.scalars(
                select(Transaction.merchant_tx_ref).where(
                    Transaction.merchant_tx_ref.in_(all_refs)
                )
            ).all()
        )

    return [ref for ref in all_refs if ref not in found_refs]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile Nomba transactions against the local DB.")
    parser.add_argument("--date-from", dest="date_from", default=None, help="YYYY-MM-DD (defaults to yesterday)")
    parser.add_argument("--date-to", dest="date_to", default=None, help="YYYY-MM-DD (defaults to today)")
    parser.add_argument("--status", dest="status", default="success", help="Transaction status filter (default: success)")
    return parser.parse_args()


def default_date_range() -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    return yesterday.isoformat(), today.isoformat()


def main() -> None:
    args = parse_args()
    default_from, default_to = default_date_range()
    date_from = args.date_from or default_from
    date_to = args.date_to or default_to

    logger.info("Starting Nomba reconciliation for %s -> %s (status=%s)", date_from, date_to, args.status)

    try:
        token = get_access_token()
    except Exception:
        logger.exception("Failed to obtain Nomba access token")
        sys.exit(1)

    try:
        transactions = fetch_transactions(token, date_from, date_to, status=args.status)
    except Exception:
        logger.exception("Failed to fetch transactions from Nomba")
        sys.exit(1)

    merchant_tx_refs = [tx["merchantTxRef"] for tx in transactions if tx.get("merchantTxRef")]
    logger.info("Fetched %d transactions (%d with merchantTxRef) from Nomba", len(transactions), len(merchant_tx_refs))

    try:
        missing_refs = find_missing_refs(merchant_tx_refs)
    except Exception:
        logger.exception("Failed to query the database for existing merchant_tx_refs")
        sys.exit(1)

    if missing_refs:
        logger.warning("%d merchantTxRef(s) NOT found in the database:", len(missing_refs))
        for ref in missing_refs:
            logger.warning("MISSING merchantTxRef=%s", ref)
    else:
        logger.info("All merchantTxRef(s) were found in the database. Nothing missing.")

    logger.info("Reconciliation complete. Log written to %s", LOG_FILE)


if __name__ == "__main__":
    main()