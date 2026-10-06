# Testing

This page is for people changing the code. If you only want to run Amiibot, you can skip it.

```bash
uv sync --group dev
uv run pytest
```

The tests are in `tests/` and mock HTTP requests and Selenium, so they don't need a network connection or Chrome. `pytest.ini` turns coverage on by default and writes `htmlcov/` and `coverage.xml`. The coverage settings (what to measure and what to leave out, such as the tests themselves) are in `pyproject.toml`. Common variations:

```bash
uv run pytest tests/test_database.py            # one file
uv run pytest tests/test_database.py::TestDatabase::test_remove_currency_us_format
uv run pytest -k currency -x                     # by name, stop at first failure
```

The 85% coverage threshold is enforced in CI only, with `--cov-fail-under=85` on the pytest command in `.github/workflows/tests.yml`. It isn't set in `pyproject.toml`, because a local run of a single test file would always fail it. To check it locally, run the whole suite with `uv run pytest --cov-fail-under=85`. Add tests with any change that touches scraping or notification logic.

## Testing against Postgres

`tests/test_database_postgres.py` runs the schema, migration and outbox code against a real Postgres. It is skipped unless `AMIIBOT_TEST_POSTGRES_URL` is set. It drops and recreates Amiibot's tables in the database it points at, so use a throwaway one:

```bash
docker run -d --rm --name amiibot-pg -p 5432:5432 -e POSTGRES_PASSWORD=test postgres:17
export AMIIBOT_TEST_POSTGRES_URL=postgresql://postgres:test@localhost:5432/postgres
uv run pytest tests/test_database_postgres.py --no-cov
```

## Lint, format and types

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

`pre-commit install` sets these up as a git hook (ruff, ruff-format, a few file hygiene checks and pyright). CI on GitHub Actions runs the same three checks. To reformat files, run `uv run ruff format .`.

## CI

`.github/workflows/tests.yml` runs on pushes and pull requests to `main` and `develop`, and can be started by hand. It has four jobs: the test suite on Python 3.13 with coverage uploaded to Codecov, the database tests against a Postgres 17 service container, ruff (lint and format check) plus pyright, and `pip-audit` for vulnerable dependencies. The actions are pinned to commit SHAs, and Dependabot (`.github/dependabot.yml`) proposes updates weekly.

## Docs

The documentation is built with MkDocs Material from `docs/`. Preview it with `uv run mkdocs serve`, and check for broken links with `uv run mkdocs build --strict`.
