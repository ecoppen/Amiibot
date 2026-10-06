"""Database tests that run against a real Postgres.

Skipped unless AMIIBOT_TEST_POSTGRES_URL is set, for example:

    AMIIBOT_TEST_POSTGRES_URL=postgresql://postgres:test@localhost:5432/postgres

The tests drop and recreate Amiibot's tables in that database for every test,
so point it at a throwaway database. CI uses a postgres:17 service container.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from config.config import DatabaseConfig
from database import (
    OUTBOX_DONE,
    OUTBOX_EXPIRED,
    OUTBOX_PENDING,
    AmiiboStock,
    Base,
    Database,
    LastScraped,
    NotificationDelivery,
    NotificationOutbox,
    ScrapingFailure,
)
from timeutil import utcnow

POSTGRES_URL = os.environ.get("AMIIBOT_TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="AMIIBOT_TEST_POSTGRES_URL is not set"
)

AMIIBOT_TABLES = [
    "amiibo_stock",
    "notification_outbox",
    "notification_deliveries",
    "last_scraped",
    "scraping_failures",
]


def _config() -> DatabaseConfig:
    assert POSTGRES_URL
    url = sa.make_url(POSTGRES_URL)
    return DatabaseConfig(
        engine="postgres",
        username=url.username,
        password=url.password,
        host=url.host or "127.0.0.1",
        port=url.port or 5432,
        name=url.database or "postgres",
    )


def _drop_tables(database: Database) -> None:
    with database.engine.begin() as conn:
        for table in AMIIBOT_TABLES:
            conn.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))


def _columns(database: Database, table: str) -> dict[str, dict]:
    inspector = sa.inspect(database.engine)
    return {col["name"]: col for col in inspector.get_columns(table)}


def _datum(url="https://t.com/1", stock="In stock", price="$19.99", release=None):
    datum = {
        "Title": f"Amiibo {url[-1]}",
        "Price": price,
        "Stock": stock,
        "URL": url,
        "Website": "t.com",
        "Image": "https://t.com/img.jpg",
        "Colour": 0x00FF00,
    }
    if release is not None:
        datum["Release"] = release
    return datum


@pytest.fixture
def database():
    db = Database(_config())
    assert db.engine.dialect.name == "postgresql"
    _drop_tables(db)
    yield db
    _drop_tables(db)
    db.engine.dispose()


@pytest.fixture
def ready(database):
    database.ensure_schema()
    return database


def _create_original_tables(database: Database) -> None:
    """Create the tables as the first release made them, without later columns."""
    statements = [
        (
            'CREATE TABLE amiibo_stock (id SERIAL PRIMARY KEY, "Website" VARCHAR NOT NULL, '
            '"Title" VARCHAR NOT NULL, "Price" VARCHAR NOT NULL, "Stock" VARCHAR NOT NULL, '
            '"Colour" VARCHAR NOT NULL, "URL" VARCHAR NOT NULL, "Image" VARCHAR NOT NULL, '
            'timestamp TIMESTAMP NOT NULL, UNIQUE ("Website", "URL"))'
        ),
        (
            "CREATE TABLE last_scraped (stockist VARCHAR NOT NULL PRIMARY KEY, "
            "timestamp TIMESTAMP NOT NULL, item_count INTEGER NOT NULL)"
        ),
        (
            "CREATE TABLE notification_outbox (id SERIAL PRIMARY KEY, "
            "website VARCHAR NOT NULL, url VARCHAR NOT NULL, title VARCHAR NOT NULL, "
            "stock_status VARCHAR NOT NULL, created_at TIMESTAMP NOT NULL)"
        ),
        (
            "CREATE TABLE scraping_failures (stockist VARCHAR NOT NULL PRIMARY KEY, "
            "consecutive_failures INTEGER NOT NULL, last_failure TIMESTAMP NOT NULL, "
            "last_success TIMESTAMP)"
        ),
    ]
    with database.engine.begin() as conn:
        for statement in statements:
            conn.execute(sa.text(statement))
        conn.execute(
            sa.text(
                'INSERT INTO amiibo_stock ("Website", "Title", "Price", "Stock", '
                '"Colour", "URL", "Image", timestamp) VALUES '
                "('t.com', 'Old', '$10', 'In stock', '1', 'https://t.com/old', "
                "'img', '2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO last_scraped VALUES ('t.com', '2026-01-02 03:04:05', 17)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO notification_outbox (website, url, title, stock_status, "
                "created_at) VALUES ('t.com', 'u', 't', 'In stock', '2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO scraping_failures VALUES ('t.com', 4, "
                "'2026-01-01 00:00:00', NULL)"
            )
        )


class TestEnsureSchema:
    def test_fresh_database_gets_every_table(self, ready):
        inspector = sa.inspect(ready.engine)
        for table in Base.metadata.tables:
            assert inspector.has_table(table)

    def test_ensure_schema_twice_is_idempotent(self, database):
        database.ensure_schema()
        before = {t: set(_columns(database, t)) for t in Base.metadata.tables}
        database.ensure_schema()
        after = {t: set(_columns(database, t)) for t in Base.metadata.tables}
        assert before == after

    def test_fresh_columns_match_the_models(self, ready):
        for name, table in Base.metadata.tables.items():
            assert set(_columns(ready, name)) == {c.name for c in table.columns}


class TestMigrationFromOldSchema:
    def test_old_schema_is_upgraded_and_keeps_its_data(self, database):
        _create_original_tables(database)

        database.ensure_schema()

        for name, table in Base.metadata.tables.items():
            assert set(_columns(database, name)) == {c.name for c in table.columns}

        with database.Session() as session:
            stock = session.query(AmiiboStock).one()
            assert stock.missed_count == 0
            assert stock.is_active is True
            assert stock.last_notified_at is None
            assert stock.first_seen_at is None

            scraped = session.query(LastScraped).one()
            # Renamed columns keep their values.
            assert scraped.last_attempt_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
            assert scraped.last_healthy_count == 17
            assert scraped.last_success_at is None
            assert scraped.consecutive_unhealthy_obs == 0

            outbox = session.query(NotificationOutbox).one()
            assert outbox.status == OUTBOX_PENDING
            assert outbox.attempts == 0
            assert outbox.price == ""
            assert outbox.image == ""
            assert outbox.colour == 0
            assert outbox.release_date is None

            failure = session.query(ScrapingFailure).one()
            assert failure.consecutive_failures == 4
            assert failure.alert_sent_at is None

    def test_migration_defaults_match_dialect_ddl(self, database):
        _create_original_tables(database)
        database.ensure_schema()
        assert "true" in str(_columns(database, "amiibo_stock")["is_active"]["default"])

    def test_migrated_schema_is_idempotent_and_usable(self, database):
        _create_original_tables(database)
        database.ensure_schema()
        database.ensure_schema()
        database._run_migrations()

        events = database.check_then_add_or_update_amiibo([_datum()])
        assert [e["URL"] for e in events] == ["https://t.com/1"]
        assert len(database.get_pending_outbox("t.com")) == 2

    def test_missing_tables_are_skipped(self, database):
        with database.engine.begin() as conn:
            conn.execute(
                sa.text(
                    "CREATE TABLE scraping_failures (stockist VARCHAR NOT NULL "
                    "PRIMARY KEY, consecutive_failures INTEGER NOT NULL, "
                    "last_failure TIMESTAMP NOT NULL, last_success TIMESTAMP)"
                )
            )
        database._run_migrations()
        inspector = sa.inspect(database.engine)
        assert not inspector.has_table("amiibo_stock")
        assert "alert_sent_at" in _columns(database, "scraping_failures")


class TestRestockEvent:
    def test_restock_emits_event_and_outbox_row(self, ready):
        ready.check_then_add_or_update_amiibo([_datum(stock="Out of Stock")])
        with ready.Session() as session:
            # Drain the "new item" row so only the restock remains.
            for row in session.query(NotificationOutbox).all():
                row.status = OUTBOX_DONE
            session.commit()

        events = ready.check_then_add_or_update_amiibo(
            [_datum(stock="In stock", release="2026-12-01")]
        )

        assert len(events) == 1
        assert events[0]["Stock"] == "In stock"
        pending = ready.get_pending_outbox("t.com")
        assert len(pending) == 1
        row = pending[0]
        assert row.stock_status == "In stock"
        assert row.url == "https://t.com/1"
        assert row.price == "$19.99"
        assert row.colour == 0x00FF00
        assert row.release_date == "2026-12-01"
        assert row.status == OUTBOX_PENDING
        assert row.attempts == 0

        with ready.Session() as session:
            item = session.query(AmiiboStock).one()
            assert item.Stock == "In stock"
            assert item.last_notified_status == "In stock"
            assert item.last_notified_at is not None

    def test_unchanged_scrape_emits_nothing(self, ready):
        ready.check_then_add_or_update_amiibo([_datum()])
        assert ready.check_then_add_or_update_amiibo([_datum()]) == []
        assert len(ready.get_pending_outbox("t.com")) == 1


class TestUTCDateTime:
    def test_round_trips_aware_utc(self, ready):
        stamp = datetime(2026, 3, 4, 5, 6, 7, 123456, tzinfo=UTC)
        with ready.Session() as session:
            session.add(
                LastScraped(
                    stockist="t.com", last_attempt_at=stamp, last_success_at=stamp
                )
            )
            session.commit()
        with ready.Session() as session:
            row = session.query(LastScraped).one()
            assert row.last_attempt_at == stamp
            assert row.last_attempt_at.tzinfo is UTC
            assert row.last_success_at == stamp

    def test_non_utc_input_is_stored_as_utc(self, ready):
        from datetime import timezone

        plus_two = timezone(timedelta(hours=2))
        stamp = datetime(2026, 3, 4, 7, 0, 0, tzinfo=plus_two)
        with ready.Session() as session:
            session.add(LastScraped(stockist="t.com", last_attempt_at=stamp))
            session.commit()
        with ready.engine.connect() as conn:
            raw = conn.execute(
                sa.text("SELECT last_attempt_at FROM last_scraped")
            ).scalar_one()
        assert raw == datetime(2026, 3, 4, 5, 0, 0)  # noqa: DTZ001 - naive UTC in the database
        with ready.Session() as session:
            assert session.query(LastScraped).one().last_attempt_at == stamp

    def test_naive_datetime_is_rejected(self, ready):
        with ready.Session() as session:
            session.add(
                LastScraped(stockist="t.com", last_attempt_at=datetime(2026, 1, 1))  # noqa: DTZ001
            )
            with pytest.raises(sa.exc.StatementError):
                session.commit()


class TestOutboxHelpers:
    def _enqueue(self, database, *items):
        database.check_then_add_or_update_amiibo(list(items))
        return database.get_pending_outbox("t.com")

    def test_get_pending_outbox_is_oldest_first_and_excludes_finished(self, ready):
        pending = self._enqueue(
            ready, _datum("https://t.com/1"), _datum("https://t.com/2")
        )
        assert len(pending) == 2
        ready.complete_outbox(pending[0].id)

        remaining = ready.get_pending_outbox("t.com")
        assert [r.id for r in remaining] == [pending[1].id]
        assert ready.get_pending_outbox("other.com") == []

    def test_mark_outbox_attempt_counts_and_timestamps(self, ready):
        (row,) = self._enqueue(ready, _datum())
        assert row.last_attempt_at is None

        before = utcnow()
        ready.mark_outbox_attempt(row.id)
        ready.mark_outbox_attempt(row.id)

        (row,) = ready.get_pending_outbox("t.com")
        assert row.attempts == 2
        assert row.last_attempt_at is not None
        assert row.last_attempt_at >= before - timedelta(seconds=1)
        assert row.last_attempt_at.tzinfo is UTC

    def test_complete_outbox_done_and_expired(self, ready):
        first, second = self._enqueue(
            ready, _datum("https://t.com/1"), _datum("https://t.com/2")
        )
        ready.complete_outbox(first.id)
        ready.complete_outbox(second.id, OUTBOX_EXPIRED)

        assert ready.get_pending_outbox("t.com") == []
        with ready.Session() as session:
            rows = {r.id: r for r in session.query(NotificationOutbox).all()}
            assert rows[first.id].status == OUTBOX_DONE
            assert rows[second.id].status == OUTBOX_EXPIRED
            assert rows[first.id].completed_at is not None

    def test_complete_outbox_rejects_unknown_status(self, ready):
        (row,) = self._enqueue(ready, _datum())
        with pytest.raises(ValueError):
            ready.complete_outbox(row.id, "pending")

    def test_helpers_ignore_unknown_ids(self, ready):
        ready.mark_outbox_attempt(999)
        ready.complete_outbox(999)

    def test_record_delivery_upserts_per_key_and_messenger(self, ready):
        args = {
            "idempotency_key": "k1",
            "website": "t.com",
            "url": "https://t.com/1",
            "title": "Amiibo 1",
            "stock_status": "In stock",
        }
        ready.record_delivery(
            messenger_name="discord", delivery_status="failed", **args
        )
        assert ready.get_delivery_status("k1", "discord") == "failed"

        ready.record_delivery(
            messenger_name="discord", delivery_status="delivered", **args
        )
        ready.record_delivery(
            messenger_name="telegram", delivery_status="delivered", **args
        )

        assert ready.get_delivery_status("k1", "discord") == "delivered"
        assert ready.get_delivery_status("k1", "telegram") == "delivered"
        assert ready.get_delivery_status("k1", "other") is None
        with ready.Session() as session:
            assert session.query(NotificationDelivery).count() == 2
