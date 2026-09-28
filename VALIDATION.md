# Verification record

Verified on 2026-09-28 for the local authentication fix:

- **32 backend tests passed**, including PostgreSQL integration tests. The session-store tests exercise actual SQLite storage, concurrent rate counts, expiry, persisted revocation, and production configuration restrictions.
- Unmocked API checks against a temporary PostgreSQL database verified seeded staff and customer login, profiles, refresh, logout, and revoked-token rejection with the development session store and no Redis.
- **4 browser tests passed** using controlled API fixtures.
- Migrations, seeding, reconciliation, and backup/restore passed. The temporary database was stopped after verification; these checks do not start the user's configured application database or validate their existing password.
- Docker Desktop could not start. Native PostgreSQL verification succeeded with `--runtime-dir 'C:/Program Files/Insta360 Studio'`.

Verified on 2026-09-25 in this workspace:

- **22 backend tests passed**, including real PostgreSQL concurrent retries, competing debits, concurrent reversal, immutable-record triggers, fee accounting, rollback, permissions, authentication, KYC, and cards. New coverage includes encrypted uploads, owner/role checks, upload limits, audited downloads, customer risk changes, approval rechecks, paginated search, card/account limits, CSV ownership, and reconciliation detecting damaged postings.
- A fresh **PostgreSQL 18.4** database accepted both Alembic migrations and the demo seed.
- Reconciliation reported no discrepancies. A PostgreSQL custom archive was created, inspected, restored into a fresh disposable database, and reconciled successfully again. Windows client binaries came from the [EDB PostgreSQL distribution](https://www.postgresql.org/download/windows/).
- A separate SQLite smoke test verified repeatable seeding, balanced opening funds, and database-level rejection of ledger edits.
- **4 browser tests passed** in Chrome: customer multipart identity uploads; staff pagination, search, risk assessment and AML approval; desktop sign-in and transfer submission; and mobile service-error handling without horizontal overflow. Browser tests use controlled API fixtures; backend behavior is covered separately.
- The **Next.js production build and TypeScript checks passed**.
- Frontend dependency installation reported **0 audit vulnerabilities**.

Docker Desktop's VM was not running and its engine did not answer requests. PostgreSQL verification therefore used a temporary native server bound to localhost, which was stopped after testing. The Docker images and full Docker Compose startup were not exercised on this machine. CI is configured to run the database tests against the deployment template's PostgreSQL 16 version.

Reproduce ordinary checks with the commands in README.md. The optional Windows helper `python -m scripts.verify_local_postgres` runs migrations, seed, reconciliation, backup/restore, and all backend tests using server binaries installed under `.tools/postgres` and client binaries under `.tools/postgres-clients/pgsql/bin` (or in the server binary directory). It accepts `--runtime-dir` for the Microsoft C++ runtime DLL directory if those DLLs are not on the system path. The restored database is created only inside that temporary server; the helper never restores over an existing application database.
