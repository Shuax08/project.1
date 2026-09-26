# THALASSERI

Kerala Food • Fresh & Traditional — a WhatsApp-first, multi-tenant Flask ordering platform.

## Run
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app server run --debug
```
Production: `gunicorn --bind 0.0.0.0:8000 server:app`

## Implemented
Application factory, SQLite/PostgreSQL configuration, tenant-scoped models and APIs, password hashing, role checks, historical order snapshots, separate payment state, idempotent order creation, safe-zone math, receipt rendering, QR/NFC public shop URLs, webhook HMAC verification, security headers, printer abstraction, reports, migrations, and deployment documentation.

Cloud printing requires a reachable network printer or local print agent; private LAN USB/Bluetooth devices cannot be reached directly by a cloud backend.

See `docs/` for installation, API, security, operations, and handover notes.
