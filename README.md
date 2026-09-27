# THALASSERI

Kerala Food • Fresh & Traditional — a WhatsApp-first, multi-tenant Flask ordering platform.

## Run
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app server run --debug
```
Initialize a fresh database with `flask --app server db upgrade`, then create an initial shop and owner with `flask --app server bootstrap --slug your-shop --name "Your Shop" --email owner@example.com`. The command prompts for a password. Log in with `POST /api/auth/login` and send its `csrf_token` as `X-CSRF-Token` for mutations. See `docs/04-whatsapp-bot.md` for live WhatsApp setup.
Production: `gunicorn --bind 0.0.0.0:8000 server:app`

## Implemented
Application factory, SQLite/PostgreSQL configuration, tenant-scoped owner APIs, password hashing, role checks, order snapshots, separate payment state, credit ledger, idempotent order creation, safe-zone math, receipt rendering, public shop URLs, webhook HMAC verification, security headers, printer abstraction, and basic reports.

**Current state:** Customer text ordering, new order notification to a linked owner, and basic linked-owner WhatsApp status commands are implemented for registered Meta Cloud API test recipients after webhook configuration. A local `simulate-whatsapp` command also exercises the conversation handlers without credentials. This is still a partial implementation, not a production-ready WhatsApp ordering SaaS. Natural language/AI commands, customer status notifications, payment gateway, printer delivery, dashboard, rate limiting, and production deployment remain incomplete. Platform administration requires a separately provisioned platform user; the bootstrap command creates only a shop owner. Never use this service for real payments or public customer traffic until these gaps are implemented and reviewed.

Cloud printing requires a reachable network printer or local print agent; private LAN USB/Bluetooth devices cannot be reached directly by a cloud backend.

See `docs/` for installation, API, security, operations, and handover notes.
