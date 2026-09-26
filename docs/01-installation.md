# Installation and deployment

Use Python 3.11+, create a virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, and set a random `SECRET_KEY`. SQLite is suitable for development; set a PostgreSQL `DATABASE_URL` in production. Run `flask --app server db upgrade` after configuring migrations, then `gunicorn --bind 0.0.0.0:8000 server:app` behind HTTPS.

Run tests with `pytest -q`. Never commit `.env` or credentials.
