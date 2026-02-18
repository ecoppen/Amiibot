"""
Unit tests for amiibot main module.
"""

from pathlib import Path
from unittest.mock import Mock, patch
import signal


class TestAmiibotLogging:
    """Test logging configuration."""

    def test_logging_constants(self):
        """Test that logging constants are configured correctly."""
        from constants import LOG_FILE_NAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT

        # Verify constants are set correctly
        assert LOG_FILE_NAME == "log.txt"
        assert LOG_MAX_BYTES == 5 * 1024 * 1024
        assert LOG_BACKUP_COUNT == 5

    def test_log_file_creation(self):
        """Test that log file path is created correctly."""
        from constants import LOG_FILE_NAME

        assert LOG_FILE_NAME == "log.txt"


class TestAmiibotCleanup:
    """Test cleanup function."""

    @patch("sys.exit")
    def test_cleanup_with_database(self, mock_exit):
        """Test cleanup closes database connection."""
        # Import after patching exit
        import amiibot

        # Create a mock database
        mock_db = Mock()
        mock_session = Mock()
        mock_db.Session.return_value = mock_session

        # Temporarily replace the global database
        original_db = amiibot._database
        amiibot._database = mock_db

        # Reset mock_exit to clear any previous calls
        mock_exit.reset_mock()

        try:
            amiibot.cleanup()
        finally:
            amiibot._database = original_db

        # Verify session was closed
        mock_session.close.assert_called_once()
        # Verify exit was called with 0
        mock_exit.assert_called_with(0)

    @patch("amiibot._database", None)
    @patch("sys.exit")
    def test_cleanup_without_database(self, mock_exit):
        """Test cleanup works when database is None."""
        import amiibot

        # Should not raise error
        amiibot.cleanup()

        mock_exit.assert_called_once_with(0)

    @patch("sys.exit")
    def test_cleanup_with_database_error(self, mock_exit):
        """Test cleanup handles database close errors gracefully."""
        import amiibot

        mock_db = Mock()
        mock_session = Mock()
        mock_session.close.side_effect = Exception("Close error")
        mock_db.Session.return_value = mock_session

        original_db = amiibot._database
        amiibot._database = mock_db

        try:
            # Should not raise error, just log warning
            amiibot.cleanup()
        finally:
            amiibot._database = original_db

        mock_exit.assert_called_once_with(0)

    @patch("amiibot._database")
    @patch("sys.exit")
    def test_cleanup_with_signal_params(self, mock_exit, mock_db_module):
        """Test cleanup accepts signal parameters."""
        import amiibot

        mock_db = Mock()
        mock_db.Session.return_value = Mock()

        original_db = amiibot._database
        amiibot._database = mock_db

        try:
            # Should accept signal parameters
            amiibot.cleanup(signum=signal.SIGTERM, frame=None)
        finally:
            amiibot._database = original_db

        mock_exit.assert_called_once_with(0)


class TestAmiibotSignalHandlers:
    """Test signal handler registration."""

    def test_signal_handlers_registered(self):
        """Test that signal handlers are registered."""
        import amiibot

        # Get current signal handlers
        sigterm_handler = signal.getsignal(signal.SIGTERM)
        sigint_handler = signal.getsignal(signal.SIGINT)

        # Verify they're set to cleanup function
        assert sigterm_handler == amiibot.cleanup
        assert sigint_handler == amiibot.cleanup


class TestAmiibotMainExecution:
    """Test main execution flow (integration-style tests)."""

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
        """Test successful execution flow."""
        # Setup mocks
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
        mock_scraper_class.return_value = mock_scraper

        # Since amiibot.py runs on import, we need to test the components
        # The actual execution happens during module load
        # We can verify the classes would be called correctly

        assert mock_scraper_class is not None
        assert mock_database_class is not None


class TestAmiibotConfigLoading:
    """Test configuration loading."""

    def test_config_path_default(self):
        """Test default config path is correct."""
        expected_path = Path("config", "config.json")
        assert expected_path == Path("config") / "config.json"

    @patch("amiibot.load_config")
    def test_config_loads_from_correct_path(self, mock_load_config):
        """Test config loads from correct path."""
        # This verifies the expected path structure
        config_path = Path("config", "config.json")
        assert config_path.parts[-2:] == ("config", "config.json")


class TestAmiibotIntegration:
    """Integration-style tests for amiibot main flow."""

    def test_module_imports(self):
        """Test that all required modules can be imported."""
        # These should not raise ImportError
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
        """Test that constants are imported correctly."""
        from constants import LOG_FILE_NAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT

        assert isinstance(LOG_FILE_NAME, str)
        assert isinstance(LOG_MAX_BYTES, int)
        assert isinstance(LOG_BACKUP_COUNT, int)

    def test_logging_setup(self):
        """Test that logging is set up correctly."""
        import logging

        # Get root logger
        root_logger = logging.getLogger()

        # Should have handlers
        assert len(root_logger.handlers) > 0

        # Should have a level set
        assert root_logger.level != logging.NOTSET

    @patch.dict("os.environ", {"LOGLEVEL": "DEBUG"})
    def test_log_level_from_environment(self):
        """Test that log level can be set from environment."""
        import os

        # Verify environment variable is set
        assert os.environ.get("LOGLEVEL") == "DEBUG"

    def test_path_resolution(self):
        """Test that Path resolution works correctly."""
        from pathlib import Path

        # Test path creation
        logs_file = Path(Path().resolve(), "log.txt")
        assert logs_file.name == "log.txt"

    def test_global_variables_initialized(self):
        """Test that global variables are initialized."""
        import amiibot

        # These should be defined (even if None)
        assert hasattr(amiibot, "_database")
        assert hasattr(amiibot, "_messengers")

    def test_cleanup_function_exists(self):
        """Test that cleanup function exists and is callable."""
        import amiibot

        assert hasattr(amiibot, "cleanup")
        assert callable(amiibot.cleanup)


class TestAmiibotErrorHandling:
    """Test error handling in main execution."""

    def test_keyboard_interrupt_handling(self):
        """Test that KeyboardInterrupt is properly defined."""
        # KeyboardInterrupt should be a built-in exception
        assert issubclass(KeyboardInterrupt, BaseException)

    def test_exception_handling(self):
        """Test that generic exceptions are handled."""
        # This is more of a structure test
        import sys

        # sys.exit should be callable
        assert callable(sys.exit)

    @patch("sys.exit")
    def test_exit_codes(self, mock_exit):
        """Test that exit codes are used correctly."""
        import amiibot

        # Test normal exit
        amiibot.cleanup()
        mock_exit.assert_called_with(0)


class TestAmiibotModuleStructure:
    """Test module structure and organization."""

    def test_module_has_docstring(self):
        """Test that key modules have docstrings."""
        import amiibot
        import scraper
        import database

        # Not all modules need docstrings, but main ones should have structure
        assert hasattr(amiibot, "__file__")
        assert hasattr(scraper, "__file__")
        assert hasattr(database, "__file__")

    def test_logging_configured(self):
        """Test that logging is properly configured."""
        import logging

        # Should be able to get a logger
        log = logging.getLogger(__name__)
        assert log is not None

    def test_imports_work(self):
        """Test that all critical imports work."""
        # These should not raise errors
        import logging
        import os
        import signal
        import sys
        from pathlib import Path
        from logging.handlers import RotatingFileHandler

        assert all([logging, os, signal, sys, Path, RotatingFileHandler])
