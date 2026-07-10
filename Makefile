.PHONY: install dev test test-live lint format type-check clean run serve docker-build docker-up docker-down

install:
	pip install -e ".[dev,web,export]" --break-system-packages

dev:
	pip install -e ".[dev]" --break-system-packages
	playwright install chromium

test:
	pytest -m "not live" -v

test-live:
	pytest -m "live" -v

lint:
	ruff check src tests

format:
	ruff format src tests

type-check:
	mypy src/book_dismantler

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build *.egg-info

run:
	python -m book_dismantler

serve:
	python -m book_dismantler serve --port 8000

docker-build:
	docker build -t book-dismantler:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down
