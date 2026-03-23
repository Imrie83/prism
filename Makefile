# Shinrai Prism Audit — Docker helpers

.PHONY: up build down restart logs shell-backend

## First run or after any code change:
build:
	docker compose up --build -d

## Start without rebuilding (fast, only if no code changed):
up:
	docker compose up -d

## Stop everything:
down:
	docker compose down

## ⚠ This does NOT pick up code changes — use 'make build' instead:
restart:
	docker compose restart

## Tail all logs:
logs:
	docker compose logs -f

## Backend logs only:
logs-backend:
	docker compose logs -f backend

## Open a shell in the backend container:
shell-backend:
	docker compose exec backend sh

## Lint the backend via Ruff:
lint-backend:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format --check .

## Format the backend via Ruff:
format-backend:
	docker compose exec backend ruff check --fix .
	docker compose exec backend ruff format .

## Show running containers:
ps:
	docker compose ps
