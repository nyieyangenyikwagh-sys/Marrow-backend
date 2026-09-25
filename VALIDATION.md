# Verification record

Verified on 2026-09-24 in this workspace:

- **18 backend tests passed**, including real PostgreSQL concurrent retries, competing debits, concurrent reversal, immutable-record triggers, fee accounting, rollback, permissions, authentication, KYC, and cards.
- A fresh **PostgreSQL 18.4** database accepted the complete Alembic migration and demo seed.
- A separate SQLite smoke test verified repeatable seeding, balanced opening funds, and database-level rejection of ledger edits.
- **2 browser tests passed** in Chrome: desktop sign-in and transfer submission, and mobile service-error handling without horizontal overflow. Browser tests use controlled API fixtures; backend behavior is covered separately.
- The **Next.js production build and TypeScript checks passed**.
- Frontend dependency installation reported **0 audit vulnerabilities**.

Docker Desktop's VM was not running and its engine did not answer requests. PostgreSQL verification therefore used a temporary native server bound to localhost, which was stopped after testing. The Docker images and full Docker Compose startup were not exercised on this machine. CI is configured to run the database tests against the deployment template's PostgreSQL 16 version.

Reproduce ordinary checks with the commands in README.md. The optional Windows helper `python -m scripts.verify_local_postgres` runs migrations, seed, and all backend tests using binaries installed under `.tools/postgres`. It accepts `--runtime-dir` for the Microsoft C++ runtime DLL directory if those DLLs are not on the system path.
