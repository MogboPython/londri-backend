# Londri

This repository is the backend API: FastAPI + PostgreSQL (PostGIS for location search) + Redis, with Nomba for payments/payouts and Twilio for WhatsApp notifications.

## Live Demo

- **Frontend:** https://londri-prototype.vercel.app
- **Backend / API docs:** https://londri-backend.fastapicloud.dev/docs

You can log into a business (owner) account on the frontend using:

```
email: mogbo18@gmail.com
password: mogbo0108
```

## Tech Stack

- **API:** FastAPI (async), Pydantic v2
- **Database:** PostgreSQL + PostGIS (via GeoAlchemy2) for geospatial laundry discovery, accessed through SQLAlchemy 2.0 (async) + Alembic migrations
- **Cache / tokens:** Redis (Nomba access/refresh token caching, bank-code caching, etc.)
- **Payments:** Nomba (virtual sub-accounts, hosted checkout/payment links, card tokenization, webhooks)
- **Notifications:** Twilio (WhatsApp Business templates), Gmail SMTP (OTP/verification emails)
- **Package management:** [uv](https://docs.astral.sh/uv/)

## Getting Started

### Prerequisites

- Python 3.13+
- PostgreSQL with the `postgis` extension available
- Redis
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Nomba sandbox account (client id/secret, webhook secret) and a Twilio account (for WhatsApp), if you want those integrations to work locally

### Install

```bash
git clone <this-repo-url>
cd backend
uv sync
```

This creates a `.venv` and installs everything pinned in `uv.lock`.

### Configure environment variables

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

`.env.example` is grouped by concern — the important ones to fill in before running locally:

- **`DATABASE_URL` / `DATABASE_SYNC_URL`** — same database, two driver flavors: `asyncpg` for the app, `psycopg2` for Alembic migrations.
- **`SECRET_KEY`** — JWT signing key. Generate one with `openssl rand -hex 32`.
- **`NOMBA_*`** — `NOMBA_BASE_URL` (sandbox by default), `NOMBA_CLIENT_ID` / `NOMBA_CLIENT_SECRET` (OAuth2 client-credentials), `NOMBA_ACCOUNT_ID` (your primary/platform account), `NOMBA_WEBHOOK_SECRET` (used to verify inbound webhook signatures).
- **`TWILIO_*`** — account SID/auth token and the WhatsApp-enabled sender number, for order/payment WhatsApp notifications.
- **`SMTP_*`** — Gmail SMTP credentials (an [app password](https://support.google.com/accounts/answer/185833), not your regular password) used for OTP and verification emails.
- **`REDIS_URL`** — defaults to a local Redis instance.
- **`FRONTEND_URL` / `ALLOWED_ORIGINS`** — used for CORS and as the callback URL handed to Nomba during checkout.

### Set up the database

Create the database and enable PostGIS (business locations are stored as `Geography` columns):

```sql
CREATE DATABASE laundry_db;
\c laundry_db
CREATE EXTENSION IF NOT EXISTS postgis;
```

Then run migrations:

```bash
uv run alembic upgrade head
```

### Run the app

```bash
uv run fastapi dev main.py
```

The API is served at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

## Testing Nomba webhooks locally

`templates/webhook.html` is a small, self-contained (client-side) tool I used to hand-craft Nomba-shaped webhook payloads, and test my running instance's webhook endpoint (`/api/v1/payment/webhook`). I left it in case webhooks doesn't reach the server from Nomba.

To use it:

1. Open `templates/webhook.html` directly in a browser.
2. Fill in your webhook endpoint URL and webhook secret.
3. Fill in the transaction details — `amount`, `customerEmail`, `orderReference` (the order or subscription ID returned when you initiated the charge), and the `order_reference_id` / `transaction_reference_id` / `operation` metadata that your create-charge call sent to Nomba.
4. Send it, and the app will process it exactly as it would a real Nomba webhook.

## Project layout

The backend follows a consistent `model → repository → service → route` layering per resource (orders, transactions, subscriptions, catalog, business, etc.):

- `app/models/` — SQLAlchemy models
- `app/repositories/` — query layer, one repository per model
- `app/services/` — business logic, orchestrates repositories and external services (Nomba, Twilio, email)
- `app/api/v1/<resource>/` — FastAPI routers + Pydantic request/response schemas

