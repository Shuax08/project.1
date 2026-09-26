# THALASSERI

Kerala Food • Fresh & Traditional — a WhatsApp-first, multi-tenant Flask ordering platform.

## Run
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app server run --debug
```
Initialize the database once with `flask --app server init-db`, then create an initial shop and owner with `flask --app server bootstrap --slug your-shop --name "Your Shop" --email owner@example.com`. The command prompts for a password. Log in with `POST /api/auth/login` and send its `csrf_token` as `X-CSRF-Token` for mutations.
Production: `gunicorn --bind 0.0.0.0:8000 server:app`

## Implemented
Application factory, SQLite/PostgreSQL configuration, tenant-scoped owner APIs, password hashing, role checks, order snapshots, separate payment state, credit ledger, idempotent order creation, safe-zone math, receipt rendering, public shop URLs, webhook HMAC verification, security headers, printer abstraction, and basic reports.

**Current state:** This is a partial implementation, not a production-ready WhatsApp ordering SaaS. The webhook verifies signatures but deliberately rejects signed messages until trusted phone-number-to-shop mapping and message processing exist. There is no customer cart/bot, owner bot, payment gateway, working printer delivery, dashboard, rate limiting, or committed database migrations. Platform administration requires a separately provisioned platform user; the bootstrap command creates only a shop owner. Never use this service for real payments or customer traffic until these gaps are implemented and reviewed.

Cloud printing requires a reachable network printer or local print agent; private LAN USB/Bluetooth devices cannot be reached directly by a cloud backend.

See `docs/` for installation, API, security, operations, and handover notes.
