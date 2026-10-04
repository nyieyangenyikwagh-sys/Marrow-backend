#!/bin/sh
set -eu

# Railway assigns the public listener port at runtime.  Running migrations here
# keeps a newly provisioned Railway PostgreSQL database in sync before serving.
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
