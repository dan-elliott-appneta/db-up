# db-up Development Guidelines

## Before Pushing to a PR

Always run type checking, linting, and tests locally before pushing changes:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run linting (uses .flake8 config)
flake8 src tests

# Run type checking (uses pyproject.toml config)
mypy src

# Run tests
pytest -v
```

All checks must pass before pushing. The CI will run the same checks and block merging if they fail.

## Quick Check Command

Run all checks at once:

```bash
flake8 src tests && mypy src && pytest -v
```

## Project Structure

- `src/db_up/` - Main source code
- `tests/` - Test suite (173 tests, 97% coverage)
- `.github/workflows/` - CI/CD workflows
- `.flake8` - Flake8 configuration
- `pyproject.toml` - Project config including mypy settings

## Installation for Development

```bash
./install.sh --venv .venv --dev
source .venv/bin/activate
```

## Python Version

This project requires Python 3.9 or higher.
