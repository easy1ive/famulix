# Development Guide

## Setup

```bash
# Clone repository
git clone <repo-url>
cd famulix

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

## Common Tasks

### Run tests

```bash
make test          # Fast tests only
make test-all      # All tests including slow/model
```

### Format code

```bash
make format        # Format and lint
make format-check  # Check only (CI)
```

### Type check

```bash
make typecheck
```

### Build package

```bash
make build
```

### Run examples

```bash
make examples
```

## Adding New Features

1. Implement the feature in `src/famulix/`
2. Add tests in `tests/`
3. Update documentation in `docs/`
4. Run `make format` and `make test`
5. Commit with conventional commit message

## Code Style

- Use type hints throughout
- Follow PEP 8 (enforced by ruff)
- Use dataclasses for data structures
- Document public functions with docstrings
- Use `round(x, 6)` for floating-point values

## Testing

- Write tests for both success and failure cases
- Use descriptive test names
- Mark slow tests with `@pytest.mark.slow`
- Mark model tests with `@pytest.mark.model`
