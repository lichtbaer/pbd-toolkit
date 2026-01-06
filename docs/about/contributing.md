# Contributing

Thank you for your interest in contributing to this fork of the PII Toolkit!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a branch for your changes
4. Make your changes
5. Test your changes
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- (Optional) Virtual environment

### Setup

```bash
# Clone repository
git clone <your-fork-url>
cd pbd-toolkit

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Recommended: install dev + feature extras (matches CI)
pip install -e ".[dev,office,images,magic,llm,gliner,spacy]"

# Optional: docs preview tooling
pip install mkdocs mkdocs-material
```

## Code Style

### Python Style

- Follow PEP 8
- Use type hints
- Write docstrings for functions and classes
- Keep functions focused and small

### Documentation

- Write documentation in English
- Update relevant documentation when adding features
- Use clear, concise language

### Commits

- Write clear commit messages
- Make atomic commits (one logical change per commit)
- Reference issues in commit messages when applicable

## Areas for Contribution

### Features

- New file format processors
- Additional PII detection patterns
- Performance improvements
- New output formats
- UI improvements

### Documentation

- Improve existing documentation
- Add examples
- Fix typos and errors
- Translate documentation

### Testing

- Add test coverage
- Improve test quality
- Add integration tests
- Test edge cases

### Bug Fixes

- Fix reported bugs
- Improve error handling
- Fix compatibility issues

## Pull Request Process

1. **Create a branch**: `git checkout -b feature/your-feature-name`
2. **Make changes**: Implement your feature or fix
3. **Test**: Run tests and verify functionality
4. **Document**: Update documentation if needed
5. **Commit**: Write clear commit messages
6. **Push**: Push to your fork
7. **Pull Request**: Create a pull request with:
   - Clear description
   - Reference to related issues
   - Screenshots (if applicable)

## Testing

Before submitting a pull request:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Lint (lightweight; CI runs Ruff)
ruff check core file_processors validators config.py matches.py main.py cli_setup.py
```

## Documentation

If adding new features:

1. Update user documentation in `docs/user-guide/`
2. Update developer documentation in `docs/developer/`
3. Add examples if applicable
4. Update `README.md` if needed

## Code Review

All contributions will be reviewed. Please:

- Be patient during review
- Respond to feedback
- Make requested changes
- Keep discussions constructive

## Questions?

If you have questions:

- Open an issue for discussion
- Check existing documentation
- Review existing code for examples

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Thank You!

Your contributions help make this project better for everyone. Thank you for taking the time to contribute!
