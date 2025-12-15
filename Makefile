.PHONY: help install install-dev test test-cov lint format clean docker-build docker-up docker-down run

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package
	pip install -e .

install-dev:  ## Install development dependencies
	pip install -e .
	pip install -r requirements-dev.txt

test:  ## Run tests
	pytest -v

test-cov:  ## Run tests with coverage report
	pytest -v --cov=src --cov-report=term-missing --cov-report=html

lint:  ## Run linters
	flake8 src tests
	mypy src

format:  ## Format code with black
	black src tests

clean:  ## Clean up generated files
	rm -rf build/ dist/ *.egg-info htmlcov/ .coverage .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

docker-build:  ## Build Docker image
	docker build -t db-up:latest .

docker-up:  ## Start services with docker-compose
	docker-compose up -d

docker-down:  ## Stop services
	docker-compose down

docker-logs:  ## Show logs from docker-compose
	docker-compose logs -f db-monitor

run:  ## Run db-up locally (requires DB_NAME and DB_PASSWORD env vars)
	python -m db_up.main

