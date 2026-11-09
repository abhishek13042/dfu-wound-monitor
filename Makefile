.PHONY: help install lint format test smoke run docker clean

help:
	@echo "DFU-WoundMonitor - development commands"
	@echo "  make install   Install runtime and dev dependencies (editable)"
	@echo "  make lint      Run ruff and mypy"
	@echo "  make format    Apply ruff auto-fixes"
	@echo "  make test      Run the test suite"
	@echo "  make smoke     Run the end-to-end smoke test (needs the checkpoint)"
	@echo "  make run       Start the API and dashboard on port 8000"
	@echo "  make docker    Build the production image"
	@echo "  make clean     Remove caches"

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	mypy src

format:
	ruff check --fix .

test:
	python -m pytest -q

smoke:
	python scripts/deployment/smoke_test.py

run:
	python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

docker:
	docker build -f docker/production/Dockerfile -t dfu-woundmonitor .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
