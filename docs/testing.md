# Testing Guide

Comprehensive guide for running tests in Amiibot.

---

## 📋 Overview

Amiibot uses **pytest** for unit testing with coverage reporting. Tests run automatically on every push to GitHub via GitHub Actions.

## Current Coverage

[![codecov](https://codecov.io/gh/ecoppen/Amiibot/branch/main/graph/badge.svg)](https://codecov.io/gh/ecoppen/Amiibot)

## Coverage Graph

![Coverage Graph](https://codecov.io/gh/ecoppen/Amiibot/branch/main/graphs/sunburst.svg)

---

## 🚀 Quick Start

```bash
# Install dependencies
uv sync --group dev

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_database.py

# Run specific test
uv run pytest tests/test_database.py::TestDatabase::test_remove_currency_us_format
```

---

## 📁 Test Structure

```
tests/
├── __init__.py
├── test_config.py          # Configuration tests
├── test_database.py        # Database tests
└── test_utils.py           # Utility function tests
```

---

## 🧪 Test Categories

### Unit Tests

Test individual functions and methods in isolation:
- **test_database.py** - Database operations, currency parsing, validation
- **test_utils.py** - Utility functions (formatting, calculations, etc.)
- **test_config.py** - Configuration loading and validation

### Integration Tests (Future)

Test interactions between components:
- Scraper → Database flow
- Database → Messenger flow
- Complete scraping cycle

---

## ⚙️ Running Tests

### Run All Tests

```bash
uv run pytest
```

### Run with Verbose Output

```bash
uv run pytest -v
```

### Run with Coverage Report

```bash
# Terminal report
uv run pytest --cov

# HTML report (opens in browser)
uv run pytest --cov --cov-report=html
open htmlcov/index.html
```

### Run Specific Tests

```bash
# Run specific file
uv run pytest tests/test_database.py

# Run specific class
uv run pytest tests/test_database.py::TestDatabase

# Run specific test
uv run pytest tests/test_database.py::TestDatabase::test_remove_currency_us_format

# Run tests matching pattern
uv run pytest -k "currency"
```

### Run with Output

```bash
# Show print statements
uv run pytest -s

# Show local variables on failure
uv run pytest -l

# Stop after first failure
uv run pytest -x

# Run last failed tests
uv run pytest --lf
```

---

## 📊 Coverage Reports

### Generate Coverage Report

```bash
# Terminal report with missing lines
uv run pytest --cov --cov-report=term-missing

# HTML report
uv run pytest --cov --cov-report=html

# XML report (for CI/CD)
uv run pytest --cov --cov-report=xml
```

### View HTML Coverage

```bash
# Generate and open HTML report
uv run pytest --cov --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage Configuration

Coverage settings are in `pytest.ini`:
- Source: All Python files
- Omit: Tests, venv, site-packages
- Exclude: Abstract methods, debug code

---

## 🎯 Writing Tests

### Test Structure

```python
import pytest

class TestMyFeature:
    """Test my feature."""

    @pytest.fixture
    def my_fixture(self):
        """Setup for tests."""
        return "test_data"

    def test_something(self, my_fixture):
        """Test something."""
        assert my_fixture == "test_data"
```

### Using Fixtures

```python
@pytest.fixture
def database(self):
    """Create test database."""
    config = DatabaseConfig(engine="sqlite", name="test_db")
    return Database(config)

def test_with_database(self, database):
    """Test using database fixture."""
    assert database is not None
```

### Testing Exceptions

```python
def test_invalid_input(self, database):
    """Test invalid input raises ValueError."""
    with pytest.raises(ValueError, match="invalid"):
        database.remove_currency("invalid")
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("$19.99", 19.99),
    ("£1,234.56", 1234.56),
    ("€10.00", 10.00),
])
def test_currency_parsing(self, database, input, expected):
    """Test various currency formats."""
    assert database.remove_currency(input) == expected
```

---

## 🤖 GitHub Actions (CI/CD)

### Automatic Testing

Tests run automatically on:
- **Push to main/develop**
- **Pull requests**
- **Manual workflow dispatch**

### Workflow Jobs

1. **Test** - Run tests on Python 3.12 and 3.13
2. **Lint** - Run ruff, black, mypy
3. **Security** - Run bandit security scanner

### View Results

Go to your repository on GitHub:
1. Click **Actions** tab
2. Select a workflow run
3. View job results and logs

### Status Badges

Add to README.md:
```markdown
![Tests](https://github.com/ecoppen/Amiibot/actions/workflows/tests.yml/badge.svg)
```

---

## 🐛 Debugging Tests

### Run with Debugging

```bash
# Drop into debugger on failure
uv run pytest --pdb

# Drop into debugger on error
uv run pytest --pdbcls=IPython.terminal.debugger:Pdb
```

### Print Debug Info

```bash
# Show print statements
uv run pytest -s

# Show local variables on failure
uv run pytest -l --tb=long

# Extra verbose
uv run pytest -vv
```

---

## 📚 Test Examples

### Database Test Example

```python
def test_update_or_insert_last_scraped(self, database):
    """Test updating last scraped timestamp."""
    stockist = "test.com"

    # First insert
    database.update_or_insert_last_scraped(stockist)

    # Verify it was inserted
    with database.Session() as session:
        record = session.query(LastScraped).filter_by(stockist=stockist).first()
        assert record is not None
        assert record.stockist == stockist
```

### Utility Function Test Example

```python
def test_format_price_thousands(self):
    """Test price formatting with thousands separator."""
    assert format_price(1234.56, "$") == "$1,234.56"
    assert format_price(12345.67, "£") == "£12,345.67"
```

### Configuration Test Example

```python
def test_config_validation_empty_stockists(self):
    """Test configuration validation with empty stockists list."""
    config_data = {...}  # Invalid config

    with pytest.raises(ValueError, match="at least one stockist"):
        load_config(temp_path)
```

---

## 🎯 Test Coverage Goals

| Component | Current | Goal |
|-----------|---------|------|
| Database | 80%+ | 90%+ |
| Utils | 90%+ | 95%+ |
| Config | 85%+ | 90%+ |
| **Overall** | **85%+** | **90%+** |

---

## 🔄 Continuous Integration

### Local Pre-commit

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### CI Pipeline

On every push:
1. ✅ Run all tests
2. ✅ Check code formatting (black)
3. ✅ Check linting (ruff)
4. ✅ Check types (mypy)
5. ✅ Security scan (bandit)
6. ✅ Generate coverage report

---

## 📖 Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Coverage.py](https://coverage.readthedocs.io/)
- [GitHub Actions](https://docs.github.com/en/actions)

---

## 🆘 Troubleshooting

### Tests Not Found

```bash
# Make sure you're in the right directory
cd /path/to/Amiibot

# Make sure pytest can find tests
uv run pytest --collect-only
```

### Import Errors

```bash
# Install dependencies
uv sync --group dev

# Check Python path
uv run python -c "import sys; print(sys.path)"
```

### Fixture Not Found

```bash
# Check fixture is defined in same file or conftest.py
# Check fixture name spelling
```

---

## ✨ Summary

- **Run tests**: `uv run pytest`
- **With coverage**: `uv run pytest --cov`
- **Verbose**: `uv run pytest -v`
- **Specific test**: `uv run pytest tests/test_database.py::test_name`
- **CI/CD**: Automatic on push via GitHub Actions
