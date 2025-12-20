"""Tests for data models."""

import pytest
from datetime import datetime
from db_up.models import (
    HealthCheckResult,
    DatabaseConfig,
    MonitorConfig,
    LoggingConfig,
    Config,
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult model."""

    def test_successful_result(self) -> None:
        """Test creating a successful health check result."""
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=45.0,
        )

        assert result.is_success()
        assert result.error_code is None
        assert result.error_message is None
        assert "45ms" in str(result)

    def test_failed_result(self) -> None:
        """Test creating a failed health check result."""
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=5000.0,
            error_code="CONNECTION_ERROR",
            error_message="Connection refused",
        )

        assert not result.is_success()
        assert result.error_code == "CONNECTION_ERROR"
        assert "Connection refused" in str(result)


class TestDatabaseConfig:
    """Tests for DatabaseConfig model."""

    def test_valid_config(self) -> None:
        """Test creating a valid database configuration."""
        config = DatabaseConfig(
            database="mydb",
            password="secret",
        )

        assert config.database == "mydb"
        assert config.password == "secret"
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.user == "postgres"
        assert config.ssl_mode == "require"

    def test_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = DatabaseConfig(
            database="testdb",
            password="testpass",
            host="db.example.com",
            port=5433,
            user="testuser",
            ssl_mode="verify-full",
        )

        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.user == "testuser"
        assert config.ssl_mode == "verify-full"

    def test_missing_database_raises_error(self) -> None:
        """Test that missing database name raises ValueError."""
        with pytest.raises(ValueError) as exc:
            DatabaseConfig(database="", password="secret")

        assert "Database name is required" in str(exc.value)
        assert "DB_NAME" in str(exc.value)

    def test_missing_password_raises_error(self) -> None:
        """Test that missing password raises ValueError."""
        with pytest.raises(ValueError) as exc:
            DatabaseConfig(database="mydb", password="")

        assert "password is required" in str(exc.value)
        assert "DB_PASSWORD" in str(exc.value)

    def test_invalid_ssl_mode_raises_error(self) -> None:
        """Test that invalid SSL mode raises ValueError."""
        with pytest.raises(ValueError) as exc:
            DatabaseConfig(
                database="mydb",
                password="secret",
                ssl_mode="invalid",
            )

        assert "Invalid ssl_mode" in str(exc.value)
        assert "require" in str(exc.value)

    def test_invalid_port_raises_error(self) -> None:
        """Test that invalid port raises ValueError."""
        with pytest.raises(ValueError) as exc:
            DatabaseConfig(
                database="mydb",
                password="secret",
                port=99999,
            )

        assert "Invalid port" in str(exc.value)

    def test_invalid_timeout_raises_error(self) -> None:
        """Test that invalid timeout raises ValueError."""
        with pytest.raises(ValueError) as exc:
            DatabaseConfig(
                database="mydb",
                password="secret",
                connect_timeout=0,
            )

        assert "connect_timeout" in str(exc.value)


class TestMonitorConfig:
    """Tests for MonitorConfig model."""

    def test_default_config(self) -> None:
        """Test creating monitor config with defaults."""
        config = MonitorConfig()

        assert config.check_interval == 60
        assert config.max_retries == 3
        assert config.retry_backoff == "exponential"
        assert config.retry_delay == 5
        assert config.retry_jitter is True
        assert config.read_only_mode is True

    def test_custom_config(self) -> None:
        """Test creating monitor config with custom values."""
        config = MonitorConfig(
            check_interval=30,
            max_retries=5,
            retry_backoff="linear",
            retry_delay=10,
            retry_jitter=False,
        )

        assert config.check_interval == 30
        assert config.max_retries == 5
        assert config.retry_backoff == "linear"

    def test_invalid_check_interval_raises_error(self) -> None:
        """Test that invalid check interval raises ValueError."""
        with pytest.raises(ValueError) as exc:
            MonitorConfig(check_interval=1)

        assert "check_interval must be between 5 and 3600" in str(exc.value)

        with pytest.raises(ValueError):
            MonitorConfig(check_interval=5000)

    def test_invalid_max_retries_raises_error(self) -> None:
        """Test that negative max_retries raises ValueError."""
        with pytest.raises(ValueError) as exc:
            MonitorConfig(max_retries=-1)

        assert "max_retries must be non-negative" in str(exc.value)

    def test_invalid_backoff_raises_error(self) -> None:
        """Test that invalid backoff strategy raises ValueError."""
        with pytest.raises(ValueError) as exc:
            MonitorConfig(retry_backoff="invalid")

        assert "Invalid retry_backoff" in str(exc.value)

    def test_health_check_query_validation(self) -> None:
        """SECURITY: Test that health check query is validated."""
        # Valid query
        config = MonitorConfig(health_check_query="SELECT 1")
        assert config.health_check_query == "SELECT 1"

        # Invalid: not a SELECT
        with pytest.raises(ValueError) as exc:
            MonitorConfig(health_check_query="DROP TABLE users")
        assert "must be a SELECT statement" in str(exc.value)

        # Invalid: contains dangerous keywords
        with pytest.raises(ValueError) as exc:
            MonitorConfig(health_check_query="SELECT 1; DELETE FROM users")
        assert "cannot contain data modification statements" in str(exc.value)


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_default_config(self) -> None:
        """Test creating logging config with defaults."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.output == "console"
        assert config.format == "text"
        assert config.redact_credentials is True
        assert config.redact_hostnames is False

    def test_custom_config(self) -> None:
        """Test creating logging config with custom values."""
        config = LoggingConfig(
            level="DEBUG",
            output="both",
            format="json",
            redact_hostnames=True,
        )

        assert config.level == "DEBUG"
        assert config.output == "both"
        assert config.format == "json"
        assert config.redact_hostnames is True

    def test_log_level_normalized(self) -> None:
        """Test that log level is normalized to uppercase."""
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"

    def test_invalid_log_level_raises_error(self) -> None:
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError) as exc:
            LoggingConfig(level="INVALID")

        assert "Invalid log level" in str(exc.value)

    def test_invalid_output_raises_error(self) -> None:
        """Test that invalid output raises ValueError."""
        with pytest.raises(ValueError) as exc:
            LoggingConfig(output="invalid")

        assert "Invalid output" in str(exc.value)

    def test_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc:
            LoggingConfig(format="invalid")

        assert "Invalid format" in str(exc.value)

    def test_invalid_file_size_raises_error(self) -> None:
        """Test that too small file size raises ValueError."""
        with pytest.raises(ValueError) as exc:
            LoggingConfig(max_file_size=100)

        assert "max_file_size must be at least 1024" in str(exc.value)


class TestConfig:
    """Tests for complete Config model."""

    def test_complete_config(self) -> None:
        """Test creating complete configuration."""
        db_config = DatabaseConfig(database="mydb", password="secret")
        monitor_config = MonitorConfig(check_interval=30)
        logging_config = LoggingConfig(level="DEBUG")

        config = Config(
            database=db_config,
            monitor=monitor_config,
            logging=logging_config,
        )

        assert config.database.database == "mydb"
        assert config.monitor.check_interval == 30
        assert config.logging.level == "DEBUG"

    def test_config_with_defaults(self) -> None:
        """Test creating config with default monitor and logging."""
        db_config = DatabaseConfig(database="mydb", password="secret")
        config = Config(database=db_config)

        assert config.monitor.check_interval == 60
        assert config.logging.level == "INFO"
