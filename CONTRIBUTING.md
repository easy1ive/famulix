# Contributing

Thanks for your interest in famulix.

## Development setup

```bash
uv venv .venv
uv pip install -e ".[dev]"
```

## Running checks

```bash
make test          # fast tests only
make test-all      # full suite (includes slow/model tests)
make format-check  # ruff format + ruff lint
make lint          # ruff lint only
make typecheck     # mypy
```

## Pull requests

- Keep commits small and focused; use conventional commit subjects.
- Every commit should build and pass `make test`.
- Add tests for new behavior; update docs for public API changes.
- New features should include an example when appropriate.

## Code style

- Formatted with `ruff format`.
- Type hints on all public functions.
- Prefer dataclasses over dicts for structured data.
