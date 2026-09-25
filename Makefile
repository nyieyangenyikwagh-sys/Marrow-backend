.PHONY: up down migrate seed test api frontend reconcile
up:
	docker compose up --build -d
down:
	docker compose down
migrate:
	python -m alembic upgrade head
seed:
	python -m scripts.seed --demo
test:
	python -m pytest -q
api:
	python -m uvicorn app.main:app --reload
frontend:
	cd banking-frontend && npm run dev
reconcile:
	python -m scripts.reconcile
