# Testing

This page is for people changing the code. If you only want to run Amiibot, you can skip it.

```bash
uv sync --group dev
uv run pytest
```

The tests are in `tests/` and mock HTTP requests and Selenium, so they don't need a network connection or Chrome. `pytest.ini` turns coverage on by default and writes `htmlcov/` and `coverage.xml`. Common variations:

```bash
uv run pytest tests/test_database.py            # one file
uv run pytest tests/test_database.py::TestDatabase::test_remove_currency_us_format
uv run pytest -k currency -x                     # by name, stop at first failure
```

`pytest.ini` has `fail_under = 85` in a `[coverage:report]` section, but coverage doesn't read settings from that file, so the threshold isn't enforced anywhere. Treat 85% as the target anyway, and add tests with any change that touches scraping or notification logic.

## Lint, format and types

```bash
uv run ruff check .
uv run black --check .
uv run pyright
```

`pre-commit install` sets these up as a git hook (ruff, ruff-format, a few file hygiene checks and pyright). CI on GitHub Actions runs ruff and `black --check` but not pyright, so run pyright yourself.

## CI

`.github/workflows/tests.yml` runs on pushes and pull requests to `main` and `develop`, and can be started by hand. It has three jobs: the test suite on Python 3.13 with coverage uploaded to Codecov, ruff plus `black --check`, and `pip-audit` for vulnerable dependencies.

## Docs

The documentation is built with MkDocs Material from `docs/`. Preview it with `uv run mkdocs serve`, and check for broken links with `uv run mkdocs build --strict`.
