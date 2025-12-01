# Test Suite

This directory contains the test suite for the PII Toolkit.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage report
```bash
pytest --cov=. --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_file_processors.py
```

### Run with verbose output
```bash
pytest -v
```

### Run only fast tests (exclude slow/integration tests)
```bash
pytest -m "not slow and not integration"
```

## Test Structure

- `test_file_processors.py` - Tests for file processors (PDF, DOCX, HTML, TXT)
- `test_matches.py` - Tests for PII matching functionality
- `test_integration.py` - Integration tests
- `conftest.py` - Shared fixtures and pytest configuration
- `fixtures/` - Test data files (if needed)

## Test Coverage

The test suite aims for >80% code coverage. Run coverage reports to see current coverage:

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
