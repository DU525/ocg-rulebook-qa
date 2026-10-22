# Thin wrappers around the commands CI runs, so "it passes locally" and
# "it passes in CI" mean the same thing.

PY ?= python
NPM ?= npm

.PHONY: help install test test-all lint fmt integrity frontend build up down logs clean

help:            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:         ## Install backend and frontend dependencies
	cd backend && $(PY) -m pip install -r requirements.txt
	cd frontend && $(NPM) ci

test:            ## Run the unit tests CI runs (fast, no model downloads)
	$(PY) -m pip install -q -r tests/requirements-ci.txt
	PYTHONPATH=backend $(PY) -m pytest tests -v

test-all:        ## Run the full backend suite (needs the full stack)
	cd backend && $(PY) -m pytest tests -v

integrity:       ## Compile every Python file and reject escaped source
	$(PY) -m compileall -q backend scripts tests
	$(PY) scripts/check_escaped_source.py $(shell git ls-files '*.py')
	@echo "source integrity: OK"

lint:            ## Lint with ruff (conservative rule set)
	$(PY) -m ruff check backend tests scripts

fmt:             ## Auto-fix what ruff can fix
	$(PY) -m ruff check --fix backend tests scripts

frontend:        ## Type-check and build the frontend
	cd frontend && $(NPM) run build

build:           ## Build all container images
	docker compose build

up:              ## Start the full stack
	docker compose up -d

down:            ## Stop the stack
	docker compose down

logs:            ## Follow backend logs
	docker compose logs -f backend

clean:           ## Remove build and test output
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage frontend/dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
