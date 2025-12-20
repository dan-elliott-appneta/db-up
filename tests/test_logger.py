"""Tests for logging module."""

import logging
import json
from db_up.logger import (
    SensitiveDataFilter,
    JSONFormatter,
    ColoredFormatter,
    setup_logging,
    get_logger,
)
from db_up.models import LoggingConfig


class TestSensitiveDataFilter:
    """Tests for SensitiveDataFilter."""

    def test_filter_redacts_password(self) -> None:
        """SECURITY: Test that passwords are redacted from log messages."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="connection failed: password=secret123",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "secret123" not in record.msg
        assert "password=***" in record.msg

    def test_filter_redacts_args(self) -> None:
        """SECURITY: Test that passwords in args are redacted."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Error: %s",
            args=("password=secret123",),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "secret123" not in record.args[0]
        assert "***" in record.args[0]

    def test_filter_redacts_hostnames_when_enabled(self) -> None:
        """Test that hostnames are redacted when enabled."""
        filter_obj = SensitiveDataFilter(redact_hostnames=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="connecting to 192.168.1.100",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert "192.168.1.100" not in record.msg

    def test_filter_allows_all_records(self) -> None:
        """Test that filter always returns True."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_basic_record(self) -> None:
        """Test formatting basic log record as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="db-up",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["message"] == "test message"
        assert data["application"] == "db-up"
        assert "timestamp" in data

    def test_format_with_extra_fields(self) -> None:
        """Test formatting record with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="db-up",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="health check passed",
            args=(),
            exc_info=None,
        )
        record.response_time_ms = 45.0
        record.status = "success"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["response_time_ms"] == 45.0
        assert data["status"] == "success"

    def test_format_with_exception(self) -> None:
        """Test formatting record with exception info."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="db-up",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestColoredFormatter:
    """Tests for ColoredFormatter."""

    def test_format_adds_colors(self) -> None:
        """Test that formatter adds color codes."""
        formatter = ColoredFormatter("%(levelname)s: %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should contain ANSI color codes
        assert "\033[" in result
        assert "test message" in result

    def test_format_preserves_levelname(self) -> None:
        """Test that original levelname is preserved."""
        formatter = ColoredFormatter("%(levelname)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        formatter.format(record)

        # Original levelname should be restored
        assert record.levelname == "INFO"


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_console_logging(self) -> None:
        """Test setting up console logging."""
        config = LoggingConfig(
            level="INFO",
            output="console",
            format="text",
        )

        logger = setup_logging(config)

        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_setup_file_logging(self, tmp_path) -> None:
        """Test setting up file logging."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="DEBUG",
            output="file",
            file_path=str(log_file),
            format="text",
        )

        logger = setup_logging(config)

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

    def test_setup_both_outputs(self, tmp_path) -> None:
        """Test setting up both console and file logging."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="WARNING",
            output="both",
            file_path=str(log_file),
        )

        logger = setup_logging(config)

        assert len(logger.handlers) == 2

    def test_setup_json_format(self) -> None:
        """Test setting up JSON format logging."""
        config = LoggingConfig(
            level="INFO",
            output="console",
            format="json",
        )

        logger = setup_logging(config)

        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_adds_sensitive_data_filter(self) -> None:
        """SECURITY: Test that sensitive data filter is added."""
        config = LoggingConfig(
            level="INFO",
            output="console",
            redact_credentials=True,
        )

        logger = setup_logging(config)

        # Check that filter is present
        filters = logger.filters
        assert len(filters) > 0
        assert isinstance(filters[0], SensitiveDataFilter)

    def test_setup_creates_log_directory(self, tmp_path) -> None:
        """Test that log directory is created if it doesn't exist."""
        log_file = tmp_path / "subdir" / "test.log"
        config = LoggingConfig(
            level="INFO",
            output="file",
            file_path=str(log_file),
        )

        setup_logging(config)

        assert log_file.parent.exists()

    def test_setup_clears_existing_handlers(self) -> None:
        """Test that existing handlers are cleared."""
        config = LoggingConfig(level="INFO", output="console")

        # Setup twice
        setup_logging(config)
        logger2 = setup_logging(config)

        # Should only have one handler, not two
        assert len(logger2.handlers) == 1

    def test_log_level_filtering(self, tmp_path) -> None:
        """Test that log level filtering works correctly."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="WARNING",
            output="file",
            file_path=str(log_file),
        )

        logger = setup_logging(config)

        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")

        # Read log file
        content = log_file.read_text()

        # Only WARNING and ERROR should be logged
        assert "debug message" not in content
        assert "info message" not in content
        assert "warning message" in content
        assert "error message" in content

    def test_log_rotation_settings(self, tmp_path) -> None:
        """Test that log rotation settings are applied."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="INFO",
            output="file",
            file_path=str(log_file),
            max_file_size=1024,
            backup_count=3,
        )

        logger = setup_logging(config)

        handler = logger.handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == 1024
        assert handler.backupCount == 3


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_same_instance(self) -> None:
        """Test that get_logger returns the same logger instance."""
        config = LoggingConfig(level="INFO", output="console")
        setup_logging(config)

        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2
        assert logger1.name == "db-up"


class TestIntegration:
    """Integration tests for logging."""

    def test_password_not_logged(self, tmp_path) -> None:
        """SECURITY: Integration test that passwords are never logged."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="INFO",
            output="file",
            file_path=str(log_file),
            format="text",
            redact_credentials=True,
        )

        logger = setup_logging(config)

        # Try to log a password
        logger.info("Connection string: postgresql://user:secret123@host/db")
        logger.error("Authentication failed with password=mysecret")

        # Read log file
        content = log_file.read_text()

        # Passwords should not be present
        assert "secret123" not in content
        assert "mysecret" not in content
        assert "***" in content

    def test_json_logging_integration(self, tmp_path) -> None:
        """Test JSON logging end-to-end."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="INFO",
            output="file",
            file_path=str(log_file),
            format="json",
        )

        logger = setup_logging(config)

        # Log with extra fields
        logger.info(
            "Health check passed",
            extra={
                "response_time_ms": 45.0,
                "status": "success",
            },
        )

        # Read and parse log file
        content = log_file.read_text()
        data = json.loads(content.strip())

        assert data["level"] == "INFO"
        assert data["message"] == "Health check passed"
        assert data["response_time_ms"] == 45.0
        assert data["status"] == "success"
