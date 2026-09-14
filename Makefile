.PHONY: install test demo up down

install:
	python -m pip install -e '.[dev]'

test:
	ruff check .
	pytest -q

demo:
	ENV_FILE=.env.demo docker compose up --build -d
	python scripts/simulate_webhook.py

up:
	docker compose up --build -d

down:
	ENV_FILE=.env.demo docker compose down
