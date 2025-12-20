"""
Data models for db-up.

This module contains all data classes used throughout the application,
including configuration models and result objects.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class HealthCheckResult:
    """
    Result of a database health check.

    This structured result object makes testing easier and provides
    a clear interface for health check outcomes.

    Attributes:
        timestamp: When the check was performed (UTC)
        status: Either "success" or "failure"
        response_time_ms: Time taken for the check in milliseconds
        error_code: Optional error code for failures (e.g., "CONNECTION_ERROR")
        error_message: Optional sanitized error message
    """

    timestamp: datetime
    status: str
    response_time_ms: float
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def is_success(self) -> bool:
        """Check if the health check was successful."""
        return self.status == "success"

    def __str__(self) -> str:
        """String representation for logging."""
        if self.is_success():
            return f"Health check passed - Response time: {self.response_time_ms:.0f}ms"
        else:
            return f"Health check failed - {self.error_code}: {self.error_message}"


@dataclass
class DatabaseConfig:
    """
    Database connection configuration.

    SECURITY: Passwords should only come from environment variables.
    This class validates that required fields are present.

    Attributes:
        database: Database name (required)
        password: Database password (required, from env var)
        host: Database host (default: localhost)
        port: Database port (default: 5432)
        user: Database user (default: postgres)
        ssl_mode: SSL mode (default: require)
        ssl_verify: Whether to verify SSL certificates (default: True)
        connect_timeout: Connection timeout in seconds (default: 5)
        statement_timeout: Statement timeout in seconds (default: 5)
        application_name: Application name for pg_stat_activity (default: db-up)
    """

    database: str
    password: str
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    ssl_mode: str = "require"
    ssl_verify: bool = True
    connect_timeout: int = 5
    statement_timeout: int = 5
    application_name: str = "db-up"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.database:
            raise ValueError(
                "Database name is required. Set DB_NAME environment variable."
            )
        if not self.password:
            raise ValueError(
                "Database password is required. Set DB_PASSWORD environment variable."
            )

        # Validate SSL mode
        valid_ssl_modes = [
            "disable",
            "allow",
            "prefer",
            "require",
            "verify-ca",
            "verify-full",
        ]
        if self.ssl_mode not in valid_ssl_modes:
            raise ValueError(
                f"Invalid ssl_mode '{self.ssl_mode}'. "
                f"Valid options: {', '.join(valid_ssl_modes)}"
            )

        # Validate port
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port {self.port}. Must be between 1 and 65535.")

        # Validate timeouts
        if self.connect_timeout < 1:
            raise ValueError("connect_timeout must be at least 1 second")
        if self.statement_timeout < 1:
            raise ValueError("statement_timeout must be at least 1 second")


@dataclass
class MonitorConfig:
    """
    Monitoring behavior configuration.

    Attributes:
        check_interval: Seconds between health checks (default: 60)
        max_retries: Maximum retry attempts on failure (default: 3)
        retry_backoff: Backoff strategy: fixed, linear, exponential
        retry_delay: Base delay between retries in seconds (default: 5)
        retry_jitter: Add randomness to retry delays (default: True)
        health_check_query: SQL query for health check
        read_only_mode: Use read-only transaction (default: True)
    """

    check_interval: int = 60
    max_retries: int = 3
    retry_backoff: str = "exponential"
    retry_delay: int = 5
    retry_jitter: bool = True
    health_check_query: str = "SELECT 1 AS health_check"
    read_only_mode: bool = True

    def __post_init__(self) -> None:
        """Validate monitoring configuration."""
        if not (5 <= self.check_interval <= 3600):
            raise ValueError("check_interval must be between 5 and 3600 seconds")

        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        valid_backoff = ["fixed", "linear", "exponential"]
        if self.retry_backoff not in valid_backoff:
            raise ValueError(
                f"Invalid retry_backoff '{self.retry_backoff}'. "
                f"Valid options: {', '.join(valid_backoff)}"
            )

        if self.retry_delay < 1:
            raise ValueError("retry_delay must be at least 1 second")

        # SECURITY: Validate health check query to prevent injection
        # Only allow simple SELECT queries
        query = self.health_check_query.strip().upper()
        if not query.startswith("SELECT"):
            raise ValueError("health_check_query must be a SELECT statement")
        if any(
            keyword in query
            for keyword in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
        ):
            raise ValueError(
                "health_check_query cannot contain data modification statements"
            )


@dataclass
class LoggingConfig:
    """
    Logging configuration.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR) (default: INFO)
        output: Output destination: console, file, both (default: console)
        file_path: Path to log file (default: logs/db-up.log)
        max_file_size: Max log file size in bytes (default: 10MB)
        backup_count: Number of rotated logs to keep (default: 5)
        format: Log format: text or json (default: text)
        redact_credentials: Redact passwords in logs (default: True)
        redact_hostnames: Redact IP addresses in logs (default: False)
    """

    level: str = "INFO"
    output: str = "console"
    file_path: str = "logs/db-up.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "text"
    redact_credentials: bool = True
    redact_hostnames: bool = False

    def __post_init__(self) -> None:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if self.level.upper() not in valid_levels:
            raise ValueError(
                f"Invalid log level '{self.level}'. "
                f"Valid options: {', '.join(valid_levels)}"
            )
        self.level = self.level.upper()

        valid_outputs = ["console", "file", "both"]
        if self.output not in valid_outputs:
            raise ValueError(
                f"Invalid output '{self.output}'. "
                f"Valid options: {', '.join(valid_outputs)}"
            )

        valid_formats = ["text", "json"]
        if self.format not in valid_formats:
            raise ValueError(
                f"Invalid format '{self.format}'. "
                f"Valid options: {', '.join(valid_formats)}"
            )

        if self.max_file_size < 1024:  # Minimum 1KB
            raise ValueError("max_file_size must be at least 1024 bytes")

        if self.backup_count < 0:
            raise ValueError("backup_count must be non-negative")


@dataclass
class MetricsConfig:
    """
    Prometheus metrics configuration.

    Attributes:
        enabled: Whether metrics collection is enabled (default: False)
        port: Port for metrics HTTP server (default: 9090)
        host: Host to bind metrics server (default: 0.0.0.0)
    """

    enabled: bool = False
    port: int = 9090
    host: str = "0.0.0.0"

    def __post_init__(self) -> None:
        """Validate metrics configuration."""
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port {self.port}. Must be between 1 and 65535.")


@dataclass
class Config:
    """
    Complete application configuration.

    This is the top-level configuration object that combines all
    configuration sections.
    """

    database: DatabaseConfig
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
