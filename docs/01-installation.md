# Installation and deployment

Use Python 3.11+, create a virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, and set a random `SECRET_KEY`. SQLite is suitable for development. Run `flask --app server init-db` to create the current schema and `flask --app server bootstrap --slug demo --name Demo --email owner@example.com` to create an initial owner. No migration scripts have been committed yet. Do not use `db upgrade` until migrations are generated and reviewed. For production, set `FLASK_ENV=production`, `SESSION_COOKIE_SECURE=true`, a PostgreSQL `DATABASE_URL` and a strong unique `SECRET_KEY`, then run `gunicorn --bind 0.0.0.0:8000 server:app` behind HTTPS after the production gaps in README are closed.

Run tests with `python -m pytest -q`. Never commit `.env` or credentials.
