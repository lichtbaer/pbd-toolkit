# Testing

This document describes the testing approach and test suite for the PII Toolkit.

## Test Structure

**Directory**: `tests/`

Test files follow the naming convention `test_*.py`:

- `test_config.py`: Configuration tests
- `test_file_processors.py`: File processor tests
- `test_integration.py`: Integration tests
- `test_matches.py`: PII match container tests
- `test_setup.py`: Setup and initialization tests

## Running Tests

### All Tests

```bash
pytest
```

### Specific Test File

```bash
pytest tests/test_config.py
```

### Specific Test

```bash
pytest tests/test_config.py::test_config_creation
```

### With Coverage

```bash
pytest --cov=. --cov-report=html
```

### Verbose Output

```bash
pytest -v
```

## Test Configuration

**File**: `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Writing Tests

### Basic Test

```python
def test_something():
    assert 1 + 1 == 2
```

### Test with Fixtures

```python
import pytest

@pytest.fixture
def sample_config():
    return Config(...)

def test_with_fixture(sample_config):
    assert sample_config.path is not None
```

### Test File Processors

```python
def test_pdf_processor():
    processor = PdfProcessor()
    assert processor.can_process('.pdf')
    assert not processor.can_process('.docx')
    
    # Test with sample file
    text = processor.extract_text('tests/sample.pdf')
    assert len(text) > 0
```

### Test Configuration

```python
def test_config_validation():
    config = Config(...)
    is_valid, error = config.validate_path()
    assert is_valid
```

### Test PII Detection

```python
def test_regex_detection():
    pmc = PiiMatchContainer()
    text = "Contact: user@example.com"
    # Process text...
    assert len(pmc.pii_matches) > 0
```

## Test Fixtures

**File**: `tests/conftest.py`

Shared fixtures for all tests:

```python
import pytest

@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for tests."""
    return tmp_path

@pytest.fixture
def sample_text_file(tmp_path):
    """Create sample text file."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Sample text content")
    return str(file_path)
```

## Integration Tests

Integration tests verify the entire workflow:

```python
def test_full_scan(tmp_path):
    # Create test files
    test_file = tmp_path / "test.txt"
    test_file.write_text("Email: test@example.com")
    
    # Run scan
    # Verify output
    # Check results
```

## Mocking

Use mocks for external dependencies:

```python
from unittest.mock import Mock, patch

@patch('gliner.GLiNER')
def test_ner_loading(mock_gliner):
    mock_model = Mock()
    mock_gliner.from_pretrained.return_value = mock_model
    
    config = Config(...)
    assert config.ner_model is not None
```

## Test Data

**Directory**: `tests/test_data/` (if exists)

Store sample files for testing:
- Sample PDFs
- Sample DOCX files
- Sample text files
- Expected outputs

## Continuous Integration

Tests should run in CI/CD:

```yaml
# Example GitHub Actions
- name: Run tests
  run: pytest
```

## Coverage Goals

Aim for:
- **Unit tests**: >80% coverage
- **Integration tests**: Cover main workflows
- **Edge cases**: Test error conditions

**Verbindungsplan:** Siehe [Testabdeckung-Verbesserungsplan](../Testabdeckung-Verbesserungsplan.md) für eine detaillierte Roadmap zur Steigerung der Coverage.

## Best Practices

1. **Isolation**: Each test should be independent
2. **Naming**: Use descriptive test names
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Fixtures**: Use fixtures for common setup
5. **Mocks**: Mock external dependencies
6. **Edge Cases**: Test error conditions
7. **Documentation**: Document complex test scenarios

## Running Specific Test Types

### Unit Tests Only

```bash
pytest tests/test_*.py -k "not integration"
```

### Integration Tests Only

```bash
pytest tests/test_integration.py
```

### Fast Tests (Skip Slow)

```bash
pytest -m "not slow"
```

## Debugging Tests

### Run with PDB

```bash
pytest --pdb
```

### Print Statements

```python
def test_debug():
    result = some_function()
    print(f"Result: {result}")  # Will show in verbose mode
    assert result is not None
```

### Verbose Output

```bash
pytest -vv
```

## Test Maintenance

- Update tests when code changes
- Add tests for new features
- Remove obsolete tests
- Keep test data up to date
- Review coverage regularly
