# KOHO Banking Core

A runnable implementation of the supplied **KOHO II.md** brief: a FastAPI API, PostgreSQL double-entry ledger, Redis session controls, and a Next.js customer and staff workspace.

The supplied document fully specifies sections 1–14 and only lists later sections. This project implements the defined core and supplies local KYC review, deterministic AML rules, sandbox cards, audit endpoints, migrations, seed data, tests, and the frontend needed to exercise it. It does not connect to real payment, card, identity-verification, or foreign-exchange networks.

## Start with Docker

Requires Docker Desktop with its Linux engine running and Node.js 22+ for the secret-generation command.

```powershell
node scripts/setup-env.mjs
docker compose up --build -d
docker compose exec api python -m scripts.seed --demo
```

`setup-env.mjs` creates random secrets and refuses to overwrite an existing `.env`. If `.env` already exists, skip that command. The seed command prompts for a password of at least 12 characters. It creates only missing users and accounts; rerunning it never resets passwords or adds funding again.

Open **http://localhost:3001**. API documentation is at **http://localhost:8000/docs**. The frontend uses port 3001 so it can coexist with an existing project on port 3000; override `FRONTEND_PORT` in `.env` if needed.

| Login | Workspace |
| --- | --- |
| `alex@example.com` | Customer, with CAD checking and savings accounts |
| `sam@example.com` | Second customer for transfers |
| `admin@koho.local` | Staff sign-in, with review and audit access |

All newly seeded users receive the password you chose. Demo opening funds are balanced against an internal clearing account through `LedgerService`; no stored balance is assigned. Use `python -m scripts.seed` without `--demo` to create only internal accounts and an administrator. Demo funding is refused in production.

## Local development

Python 3.12+, Node.js 22+, PostgreSQL 16, and Redis 7 are expected. PostgreSQL and Redis can run in Docker while the API and frontend run locally:

```powershell
docker compose up -d postgres redis
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m scripts.seed --demo
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd banking-frontend
npm ci
npm run dev -- --port 3001
```

This workspace also contains a locally downloaded Python toolchain under the ignored `.tools` directory and a `.venv`; these are not application dependencies to commit. The frontend proxies `/api/*` to FastAPI at `http://127.0.0.1:8000/api/v1/*`. Set `API_INTERNAL_URL` if the backend is elsewhere. The browser never accesses a database.

## What works

- Customer signup, separate customer/staff login, Argon2 password hashing, expiring JWT access tokens, role-preserving refresh tokens, and Redis-backed refresh revocation and authentication throttling.
- Customer profiles, staff directory, role-gated freezes, account creation, limits, account freezing/unfreezing, and zero-balance closure.
- Same-currency transfers in CAD, USD, GBP, and EUR; positive two-decimal amounts; a configurable 1% fee; live ledger balances; statements; and transaction history.
- Sender ownership checks, active/verified parties, per-transaction/daily/monthly limits including fees, and insufficient-funds checks.
- Caller-required idempotency keys scoped to the source account. PostgreSQL advisory locks serialize retries; unique constraints are the final guard. Reusing a key with changed request data is rejected. Redis caches transaction IDs only; status is read from PostgreSQL so reversals cannot leave stale cached responses.
- Sorted account locks, atomic posting, four ledger legs when fees are nonzero, and two legs for amounts whose rounded fee is zero.
- Transfers of 10,000 or more enter manual review. High-risk customers produce failed requests and an AML record without moving funds. Approval rechecks balances, status, identity, and limits under locks. Pending requests do not reserve funds.
- Reversal creates a new transaction and opposite ledger entries, including the fee. Original entries stay intact. Reversal cannot overdraw a customer, and the original transaction can be reversed only once.
- Manual KYC submission/review with encrypted document numbers, references, and uploaded files. The UI accepts PNG/JPEG images and PDF documents, up to 5 MB per file; selfies must be images. Upload references are checked for owner and document role. Staff downloads require compliance/admin authorization and create audit events. Existing HTTP(S) references remain supported by the API; the server never fetches them. There is no automated identity verification or malware scanning.
- Sandbox card creation, freezing/unfreezing, editable limits, and permanent cancellation from the UI. No actual PAN or CVV is issued or stored, and card limits are metadata until a card-network integration exists.
- Paginated staff customer/account directories, identity and transfer queues, AML checks, and searchable append-only audit history. Compliance staff can record risk assessments; high-risk customers cannot have pending transfers approved until reassessed. Support staff have read-only customer directory access.
- Health checks, Prometheus metrics, request IDs, responsive customer and staff screens, JSON statements, and CSV exports with selectable UTC date ranges, opening/closing balances, and formula-safe descriptions.
- Read-only reconciliation and PostgreSQL custom-archive backup utilities, with a disposable-database restore verification helper.

## Ledger and security boundaries

`app/api/v1` handles HTTP and authorization; `app/services` owns business rules; `LedgerService` is the financial writer. Money is `Decimal` in Python, `NUMERIC(20,2)` in PostgreSQL, and strings in JSON. No account has a balance column.

The initial migration installs PostgreSQL triggers rejecting ledger/audit updates and deletes, protecting transaction financial fields and state transitions, verifying ledger account ownership/currency, and checking balanced postings at commit. SQLite is used only for fast functional tests; it does **not** prove PostgreSQL locking or deferred-trigger behavior.

Session tokens remain in browser memory and are lost on page refresh. Refresh tokens retain customer/staff identity and are revoked on logout; already-issued access tokens expire after 30 minutes. Redis is configured with persistence and `noeviction`, because eviction of revoked-token records would undermine logout. Do not flush production Redis as if it were a disposable cache.

This is a development banking system, not a certified or audited banking product. External deposits/withdrawals, payment-network settlement, FX, automated sanctions/identity vendors, MFA, password recovery, and production operational controls remain separate integrations. The seed is the only demo-funding path; there is no public mint-money endpoint.

## Tests

```powershell
.venv/Scripts/python.exe -m pytest -q
cd banking-frontend
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

The Python suite tests money invariants and API permissions. Browser tests use explicitly mocked API responses to exercise UI behavior; they are not a substitute for backend integration tests.

See [VALIDATION.md](VALIDATION.md) for the completed checks and environment limitations. CI runs the backend suite against PostgreSQL 16 and verifies the frontend build and browser flows.

To additionally run real PostgreSQL concurrency and database-trigger tests, point `TEST_DATABASE_URL` at a disposable test database:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://banking:banking@localhost:5432/banking_core'
.venv/Scripts/python.exe -m pytest -q tests/test_postgres.py
```

These tests create and remove uniquely named schemas and leave existing tables alone. They test concurrent duplicate requests, competing withdrawals through transfers, and concurrent reversal. Without this variable, PostgreSQL tests are explicitly skipped.

## Production deployment template

`docker-compose.prod.yml` is a separate deployment template, with private database ports, secret interpolation, a one-shot migration service, four API workers, Redis persistence, and an HTTPS Nginx proxy. Supply strong `DB_PASSWORD` and `REDIS_PASSWORD` in `.env`, set your `CORS_ORIGINS`, and provide `certs/fullchain.pem` and `certs/privkey.pem`. Database passwords must be URL-safe (the setup script uses hexadecimal values). Start with:

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

Arrange off-host PostgreSQL backups and restore drills, key rotation, monitoring, and an independent security review before connecting real financial services. `/metrics` is denied by the public production proxy and is intended for internal scraping. Store encryption-key backups securely: losing that key makes stored KYC references unreadable. Do not run destructive migration downgrades against financial records.

## Main endpoints

| Area | Endpoints under `/api/v1` |
| --- | --- |
| Auth | `/auth/signup`, `/auth/login`, `/auth/admin/login`, `/auth/refresh`, `/auth/logout` |
| Customer | `/customers/me`, `/customers`, `/customers/{id}/freeze`, `/customers/{id}/unfreeze` |
| Accounts | `/accounts`, `/accounts/me`, `/accounts/{id}`, `/accounts/{id}/limits`, `/freeze`, `/unfreeze`, `/close` |
| Money | `/transactions/transfer`, `/transactions`, `/transactions/{id}`, `/{id}/review/approve`, `/{id}/review/reject`, `/{id}/reverse` |
| Ledger | `/ledger/{account_id}/balance`, `/entries`, `/statement?start=…&end=…`, `/statement-csv?start=…&end=…` |
| Identity | `/kyc/attachments`, `/kyc/documents`, `/kyc/status`, `/kyc/{id}/review` |
| Cards | `/cards`, `/cards/{id}/status`, `/cards/{id}/limits` |
| Operations | `/admin/me`, `/admin/summary`, `/admin/customers`, `/admin/customers/{id}/risk`, `/admin/accounts`, `/admin/transactions`, `/admin/kyc`, `/admin/attachments/{id}`, `/admin/aml`, `/admin/audit` |

Use the generated OpenAPI documentation for exact schemas and full paths. Staff workbenches page through 25 records at a time; transaction history uses 50. Customer, account and audit directories support server-side search. Limits accept explicit `null` to remove a limit; omitted fields remain unchanged.

## Updates and operational commands

Existing databases need the encrypted-attachments migration before using the new identity form:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m scripts.reconcile
.venv/Scripts/python.exe -m scripts.backup backups/banking.dump
```

Reconciliation uses a read-only repeatable-read PostgreSQL snapshot and exits with code 1 when it finds unbalanced postings, missing/extra transaction legs, ownership/currency mismatches, or negative customer balances. This checks internal accounting; external settlement reconciliation needs an external payment provider.

Backup requires `pg_dump` and `pg_restore` on PATH, or `--bin-dir` pointing to a compatible PostgreSQL client directory. It uses `DATABASE_URL`, keeps the database password out of command arguments, refuses to overwrite files, and checks the archive with `pg_restore --list`. A failed invocation may leave an incomplete archive; only a successful verification reports it as verified. Archives contain sensitive database data and must be protected and copied to controlled off-host storage. Back up `ENCRYPTION_KEY` separately; losing it makes identity numbers and files unreadable. Restore into a fresh, isolated database with `pg_restore --exit-on-error --dbname <restore_database> <archive>`, then run reconciliation against that database before considering recovery complete. The local verification helper performs this restore drill automatically against a disposable server.

Identity uploads are stored as encrypted database blobs, so they are included in database backups. Each customer is limited to 20 uploads. This sandbox has no deletion/retention administration or object-storage integration; define those policies before collecting real documents. The existing `KYC_DOCUMENT_STORAGE_PATH` setting is reserved and is not used by database-backed uploads.
