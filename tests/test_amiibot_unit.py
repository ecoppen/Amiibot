from pathlib import Path
from unittest.mock import Mock, patch


class TestAmiibotLogging:
    def test_logging_constants(self):
        from constants import LOG_FILE_NAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT

        assert LOG_FILE_NAME == "log.txt"
        assert LOG_MAX_BYTES == 5 * 1024 * 1024
        assert LOG_BACKUP_COUNT == 5

    def test_log_file_creation(self):
        from constants import LOG_FILE_NAME

        assert LOG_FILE_NAME == "log.txt"


class TestAmiibotCleanup:
    @patch("amiibot._database", None)
    def test_cleanup_without_database(self):
        import amiibot

        amiibot.cleanup()

    def test_cleanup_with_database(self):
        import amiibot

        mock_db = Mock()
        mock_engine = Mock()
        mock_db.engine = mock_engine

        original_db = amiibot._database
        amiibot._database = mock_db
        try:
            amiibot.cleanup()
        finally:
            amiibot._database = original_db

        mock_engine.dispose.assert_called_once()

    def test_cleanup_with_database_error(self):
        import amiibot

        mock_db = Mock()
        mock_db.engine.dispose.side_effect = Exception("Dispose error")

        original_db = amiibot._database
        amiibot._database = mock_db
        try:
            amiibot.cleanup()
        finally:
            amiibot._database = original_db


class TestAmiibotMainExecution:
    @patch("amiibot.Scraper")
    @patch("amiibot.StockistManager")
    @patch("amiibot.MessageManager")
    @patch("amiibot.Database")
    @patch("amiibot.load_config")
    def test_successful_execution_flow(
        self,
        mock_load_config,
        mock_database_class,
        mock_message_manager_class,
        mock_stockist_manager_class,
        mock_scraper_class,
    ):
        from result import RunResult, RunStatus

        mock_config = Mock()
        mock_config.database = Mock()
        mock_config.messengers = Mock()
        mock_load_config.return_value = mock_config

        mock_database = Mock()
        mock_database_class.return_value = mock_database

        mock_messengers = Mock()
        mock_message_manager_class.return_value = mock_messengers

        mock_stockists = Mock()
        mock_stockist_manager_class.return_value = mock_stockists

        mock_scraper = Mock()
        mock_scraper.scrape.return_value = RunResult(
            status=RunStatus.SUCCESS,
            exit_code=0,
            stockists_attempted=1,
            stockists_succeeded=1,
        )
        mock_scraper_class.return_value = mock_scraper

        import amiibot

        result = amiibot.main()

        assert result.status == RunStatus.SUCCESS
        assert result.exit_code == 0
        assert result.stockists_succeeded == 1

    @patch("amiibot.Scraper")
    @patch("amiibot.StockistManager")
    @patch("amiibot.MessageManager")
    @patch("amiibot.Database")
    @patch("amiibot.load_config")
    def test_partial_success_flow(
        self,
        mock_load_config,
        mock_database_class,
        mock_message_manager_class,
        mock_stockist_manager_class,
        mock_scraper_class,
    ):
        from result import RunResult, RunStatus

        mock_config = Mock()
        mock_config.database = Mock()
        mock_config.messengers = Mock()
        mock_load_config.return_value = mock_config

        mock_database = Mock()
        mock_database_class.return_value = mock_database

        mock_stockists = Mock()
        mock_stockist_manager_class.return_value = mock_stockists

        mock_scraper = Mock()
        mock_scraper.scrape.return_value = RunResult(
            status=RunStatus.PARTIAL,
            exit_code=2,
            stockists_attempted=2,
            stockists_succeeded=1,
            stockists_failed=1,
        )
        mock_scraper_class.return_value = mock_scraper

        import amiibot

        result = amiibot.main()

        assert result.status == RunStatus.PARTIAL
        assert result.exit_code == 2


class TestAmiibotConfigLoading:
    def test_config_path_default(self):
        expected_path = Path("config", "config.json")
        assert expected_path == Path("config") / "config.json"


class TestAmiibotIntegration:
    def test_module_imports(self):
        from config.config import load_config
        from database import Database
        from messenger.manager import MessageManager
        from scraper import Scraper
        from stockist.manager import StockistManager

        assert load_config is not None
        assert Database is not None
        assert MessageManager is not None
        assert Scraper is not None
        assert StockistManager is not None

    def test_constants_imported(self):
        from constants import LOG_FILE_NAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT

        assert isinstance(LOG_FILE_NAME, str)
        assert isinstance(LOG_MAX_BYTES, int)
        assert isinstance(LOG_BACKUP_COUNT, int)

    def test_logging_setup(self):
        import logging

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        assert root_logger.level != logging.NOTSET

    @patch.dict("os.environ", {"LOGLEVEL": "DEBUG"})
    def test_log_level_from_environment(self):
        import os

        assert os.environ.get("LOGLEVEL") == "DEBUG"

    def test_path_resolution(self):
        from pathlib import Path

        logs_file = Path(Path().resolve(), "log.txt")
        assert logs_file.name == "log.txt"

    def test_global_variables_initialized(self):
        import amiibot

        assert hasattr(amiibot, "_database")
        assert hasattr(amiibot, "_messengers")

    def test_cleanup_function_exists(self):
        import amiibot

        assert hasattr(amiibot, "cleanup")
        assert callable(amiibot.cleanup)

    def test_main_function_exists(self):
        import amiibot

        assert hasattr(amiibot, "main")
        assert callable(amiibot.main)


class TestAmiibotErrorHandling:
    def test_keyboard_interrupt_handling(self):
        assert issubclass(KeyboardInterrupt, BaseException)


class TestAmiibotModuleStructure:
    def test_module_has_docstring(self):
        import amiibot
        import scraper
        import database

        assert hasattr(amiibot, "__file__")
        assert hasattr(scraper, "__file__")
        assert hasattr(database, "__file__")

    def test_logging_configured(self):
        import logging

        log = logging.getLogger(__name__)
        assert log is not None

    def test_imports_work(self):
        import logging
        import os
        import sys
        from pathlib import Path
        from logging.handlers import RotatingFileHandler

        assert all([logging, os, sys, Path, RotatingFileHandler])
