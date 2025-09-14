# Makefile for agentic-memories

.PHONY: help install test test-unit test-e2e start stop clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run all tests
	pytest -q

test-unit: ## Run unit tests only
	pytest tests/ -k "not e2e" -q

test-e2e: ## Run E2E tests against deployed app
	./tests/e2e/run_e2e_tests.sh

start: ## Start the application
	docker-compose up -d

stop: ## Stop the application
	docker-compose down

clean: ## Clean up logs and results
	rm -rf tests/e2e/logs/ tests/e2e/results/
	docker-compose down -v

dev: ## Start development environment
	docker-compose up -d
	@echo "Application started at http://localhost:8080"
	@echo "Run 'make test-e2e' to run E2E tests"
