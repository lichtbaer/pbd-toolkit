# Test Suite

This directory contains the test suite for the pbD Toolkit.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage report (not on by default; CI passes these flags)
```bash
pytest --cov=. --cov=scripts --cov-report=term-missing
```

### Reproduce an order-dependent failure (pytest-randomly prints the seed)
```bash
pytest -p randomly --randomly-seed=12345
```

### Run specific test file
```bash
pytest tests/test_file_processors.py
```

### Run with verbose output
```bash
pytest -v
```

### Run only unit tests (exclude integration tests)
```bash
pytest -m "not integration"
```

## Test Structure

- `test_file_processors.py` - Tests for file processors (PDF, DOCX, HTML, TXT)
- `test_matches.py` - Tests for PII matching functionality
- `test_integration.py` - Integration tests
- `test_validators.py` - Hypothesis property tests for IBAN / Luhn / BIC / tax-ID checksums
- `test_scan_cache.py` - Incremental-scan cache invalidation contract
- `conftest.py` - Shared fixtures; use `make_config` / `real_config` (real `Config`) in new tests
- `fixtures/` - Test data files (if needed)

## Test Coverage

The test suite aims for >80% code coverage long-term. CI enforces a ratcheting
floor via `fail_under` in `pyproject.toml` (`[tool.coverage.report]`) — currently
65%, just below the ~67% measured after the #93 coverage push. Raise the floor
as coverage improves; never lower it without explicit justification. Run
coverage reports to see current coverage:

```bash
pytest --cov=. --cov-report=term-missing
```

## Writing New Tests

When adding new functionality, please add corresponding tests:

1. Unit tests for individual functions/classes
2. Integration tests for end-to-end scenarios
3. Update fixtures if new test data is needed

## Continuous Integration

Tests should pass before committing. Consider setting up pre-commit hooks or CI/CD to enforce this.
