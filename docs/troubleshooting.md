# Troubleshooting

## Common Issues

### Build fails with "hatchling not found"

Install the dev extra which includes the build backend:

```bash
pip install -e ".[dev]"
```

### Tests fail with "torch not found"

Torch is optional. Skip model tests:

```bash
make test  # Fast tests only (no torch needed)
```

Or install with torch:

```bash
pip install -e ".[dev,torch]" --extra-index-url https://download.pytorch.org/whl/cpu
```

### Import errors after install

Ensure you're using the project's virtual environment:

```bash
source .venv/bin/activate
```

### Format check fails

Run the formatter:

```bash
make format
```

### Type check fails

Run mypy to see errors:

```bash
make typecheck
```

## Performance

### Slow tests

Mark genuinely slow tests with `@pytest.mark.slow`:

```python
@pytest.mark.slow
def test_large_scale():
    ...
```

Run fast tests only:

```bash
make test
```

### Large memory graphs

For graphs with >10k nodes, consider:
- Increasing consolidation `dedup_threshold` to reduce merges
- Using smaller `top_k` for retrieval
- Reducing context `budget` for faster assembly

## Debugging

### Enable verbose output

```bash
pytest -v tests/
```

### Check tree receipts

Every commit's build/test/format results are recorded:

```bash
cat .git/validation/<tree-hash>.json
```

### Replay a session

```bash
famulix replay session.jsonl
```
