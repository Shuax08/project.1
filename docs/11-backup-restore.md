For PostgreSQL, use `pg_dump "$DATABASE_URL" > backup.sql` and restore with `psql "$DATABASE_URL" < backup.sql`. Schedule encrypted daily backups, retention, and restore tests.
