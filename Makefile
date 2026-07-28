.PHONY: setup api client check learning-check docker-up docker-down

setup:
	cd backend && uv sync
	cd apps/client && npm install

api:
	cd backend && uv run uvicorn app.main:app --reload

client:
	cd apps/client && npm run start

check:
	cd backend && uv run ruff check . && uv run pytest
	cd apps/client && npm run typecheck && npm run test && npm run export:web

learning-check:
	cd backend && uv run pytest -m user_owned

docker-up:
	docker compose up --build

docker-down:
	docker compose down
