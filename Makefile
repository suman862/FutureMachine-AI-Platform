install:
	python -m pip install -e ".[dev]"

format:
	ruff format .

lint:
	ruff check .

typecheck:
	mypy gateway

security:
	bandit -r gateway services -ll

test:
	pytest -q

check: format lint typecheck security test

compose-up:
	docker compose up --build

compose-down:
	docker compose down -v
