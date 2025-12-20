# db-up Development Guidelines

## Before Pushing to a PR

Always run type checking, linting, and tests locally before pushing changes:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run linting (flake8)
flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics

# Run type checking (mypy)
mypy src --ignore-missing-imports

# Run tests
pytest -v
```

All checks must pass before pushing. The CI will run the same checks and block merging if they fail.

## Quick Check Command

Run all checks at once:

```bash
flake8 src tests --select=E9,F63,F7,F82 && mypy src --ignore-missing-imports && pytest -v
```

## Project Structure

- `src/db_up/` - Main source code
- `tests/` - Test suite (173 tests, 97% coverage)
- `.github/workflows/` - CI/CD workflows

## Installation for Development

```bash
./install.sh --venv .venv --dev
source .venv/bin/activate
```
