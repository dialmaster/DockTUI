.PHONY: help install format lint test check all clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	poetry install

format:  ## Format code with autoflake, isort, and black
	poetry run autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive dockerview/
	poetry run isort dockerview/
	poetry run black dockerview/

lint:  ## Check code formatting without making changes
	poetry run autoflake --check --remove-all-unused-imports --remove-unused-variables --recursive dockerview/
	poetry run isort --check-only dockerview/
	poetry run black --check dockerview/

test:  ## Run tests
	poetry run pytest -v

check: lint test  ## Run all checks (lint + test)

all: format test  ## Format code and run tests

clean:  ## Clean up cache files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info