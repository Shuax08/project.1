# Installation and deployment

Use Python 3.11+, create a virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, and set a random `SECRET_KEY`. SQLite is suitable for development. For a fresh database run `flask --app server db upgrade` and `flask --app server bootstrap --slug demo --name Demo --email owner@example.com`. An initial Alembic migration is included. If you have an existing database from an earlier revision, back it up first; stamping requires checking that its schema matches the initial migration. For production, set `FLASK_ENV=production`, `SESSION_COOKIE_SECURE=true`, a PostgreSQL `DATABASE_URL` and a strong unique `SECRET_KEY`, then run `gunicorn --bind 0.0.0.0:8000 server:app` behind HTTPS after the production gaps in README are closed.

Run tests with `python -m pytest -q`. Never commit `.env` or credentials.
