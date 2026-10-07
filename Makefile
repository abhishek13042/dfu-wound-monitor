.PHONY: help install lint format test clean

help:
	@echo "DFU-WoundMonitor - Development Commands"
	@echo "  make install     Install package in editable mode with dev dependencies"
	@echo "  make lint        Run static analysis and linting checks"
	@echo "  make format      Format codebase with black and ruff"
	@echo "  make test        Run test suite"
	@echo "  make clean       Remove temporary files and Python caches"

install:
	pip install -e .[dev]

lint:
	ruff check .
	mypy src tests

format:
	ruff format .
	black .

test:
	pytest tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
