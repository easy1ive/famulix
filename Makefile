PYTHON := .venv/bin/python

.PHONY: build test test-all format format-check lint typecheck release clean

build:
	$(PYTHON) -m build --wheel --no-isolation

test:
	$(PYTHON) -m pytest -q -m "not slow"

test-all:
	$(PYTHON) -m pytest -q

format:
	$(PYTHON) -m ruff format src tests examples scripts
	$(PYTHON) -m ruff check --fix src tests examples scripts

format-check:
	$(PYTHON) -m ruff format --check src tests examples scripts
	$(PYTHON) -m ruff check src tests examples scripts

lint:
	$(PYTHON) -m ruff check src tests examples scripts

typecheck:
	$(PYTHON) -m mypy src/famulix

release: build
	@echo "Release wheel built in dist/"

clean:
	rm -rf build dist src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
