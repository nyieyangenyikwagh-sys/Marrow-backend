# Railway deployment

Create four Railway services in one project: **Postgres**, **Redis**,
**marrow-backend**, and **banking-frontend**. Deploy the backend from the
repository root. Deploy the frontend from the same repository with **Root
Directory** set to `banking-frontend`.

The included `railway.toml` files set the health checks. The backend entrypoint
now runs database migrations and listens on Railway's runtime `PORT`.

## Backend variables

In the `marrow-backend` service, add these variables. Replace service names if
your Railway Postgres or Redis services use different names.

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ENVIRONMENT=production
SESSION_BACKEND=redis
SECRET_KEY=<a new random value of at least 32 characters>
ENCRYPTION_KEY=<a Fernet key generated with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
CORS_ORIGINS=https://<your-frontend-domain>.up.railway.app
```

Railway's PostgreSQL URL is accepted directly; the application converts it to
the async SQLAlchemy driver format. Do not set `DB_PASSWORD` or
`REDIS_PASSWORD` for this Railway setup.

Generate a public domain for the backend, then confirm:

```text
https://<your-backend-domain>/health
```

It must return `{"status":"ok"}` before testing the frontend.

## Frontend variables

In the `banking-frontend` service, set the server-only proxy URL:

```text
API_INTERNAL_URL=https://<your-backend-domain>.up.railway.app
```

The existing `NEXT_PUBLIC_API_URL` is not read by this application. Its client
uses `/api/*`, and the Next.js route proxy uses `API_INTERNAL_URL`; without
that variable it tries `http://127.0.0.1:8000` inside the frontend container
and correctly returns a 503.

Generate a public domain for the frontend. Copy that exact HTTPS origin into
the backend `CORS_ORIGINS` value and redeploy the backend once.

## If a deploy fails

- A backend log ending before Uvicorn starts usually means an invalid or missing
  `SECRET_KEY`, `ENCRYPTION_KEY`, `DATABASE_URL`, or `REDIS_URL`.
- A backend health response of `{"status":"unavailable"}` means Railway can
  reach the app but Postgres or Redis is not connected. Check that the service
  variable references match the actual Railway service names.
- A frontend login 503 with a healthy backend means `API_INTERNAL_URL` is
  missing, misspelled, or points to a backend domain without `https://`.
