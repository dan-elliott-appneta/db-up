"""
Configuration loading and management for db-up.

This module handles loading configuration from multiple sources:
1. Environment variables (highest priority)
2. YAML configuration file
3. Default values (lowest priority)

SECURITY: Passwords must only come from environment variables.
"""

import os
import yaml
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from db_up.models import (
    Config,
    DatabaseConfig,
    MonitorConfig,
    LoggingConfig,
    MetricsConfig,
)


def load_config(config_file: Optional[str] = None) -> Config:
    """
    Load configuration from environment variables and optional config file.

    Priority order:
    1. Environment variables (highest)
    2. Config file
    3. Defaults (lowest)

    Args:
        config_file: Optional path to YAML config file

    Returns:
        Complete Config object

    Raises:
        ValueError: If required configuration is missing or invalid
    """
    # Load .env file if it exists
    load_dotenv()

    # Load config file if provided
    file_config: Dict[str, Any] = {}
    if config_file:
        file_config = _load_yaml_config(config_file)

    # Build configuration with priority: env > file > defaults
    database_config = _load_database_config(file_config.get("database", {}))
    monitor_config = _load_monitor_config(file_config.get("monitor", {}))
    logging_config = _load_logging_config(file_config.get("logging", {}))
    metrics_config = _load_metrics_config(file_config.get("metrics", {}))

    return Config(
        database=database_config,
        monitor=monitor_config,
        logging=logging_config,
        metrics=metrics_config,
    )


def _load_yaml_config(config_file: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_file: Path to YAML config file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    config_path = Path(config_file)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_file}\n"
            f"Create a config file or use environment variables."
        )

    # SECURITY: Check file permissions (warn if world-readable)
    if os.name != "nt":  # Unix/Linux only
        stat_info = config_path.stat()
        if stat_info.st_mode & 0o004:  # World-readable
            print(
                f"WARNING: Config file {config_file} is world-readable. "
                f"This may expose sensitive information. "
                f"Run: chmod 600 {config_file}"
            )

    with open(config_path, "r") as f:
        try:
            config = yaml.safe_load(f)
            return config or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_file}: {e}")


def _load_database_config(file_config: Dict[str, Any]) -> DatabaseConfig:
    """
    Load database configuration with environment variable priority.

    SECURITY: Password must come from environment variable.

    Args:
        file_config: Database section from config file

    Returns:
        DatabaseConfig object
    """
    # Check for DATABASE_URL first (Heroku/cloud compatible)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return _parse_database_url(database_url)

    # Otherwise, load individual parameters
    # Priority: env var > file > default
    database = os.getenv("DB_NAME") or file_config.get("name", "")
    password = os.getenv("DB_PASSWORD", "")  # SECURITY: Only from env
    host = os.getenv("DB_HOST") or file_config.get("host", "localhost")
    port = int(os.getenv("DB_PORT", file_config.get("port", 5432)))
    user = os.getenv("DB_USER") or file_config.get("user", "postgres")
    ssl_mode = os.getenv("DB_SSL_MODE") or file_config.get("ssl_mode", "require")
    ssl_verify = _parse_bool(
        os.getenv("SSL_VERIFY"), file_config.get("ssl_verify", True)
    )
    connect_timeout = int(
        os.getenv("DB_CONNECT_TIMEOUT", file_config.get("connect_timeout", 5))
    )
    statement_timeout = int(
        os.getenv("DB_STATEMENT_TIMEOUT", file_config.get("statement_timeout", 5))
    )
    application_name = file_config.get("application_name", "db-up")

    return DatabaseConfig(
        database=database,
        password=password,
        host=host,
        port=port,
        user=user,
        ssl_mode=ssl_mode,
        ssl_verify=ssl_verify,
        connect_timeout=connect_timeout,
        statement_timeout=statement_timeout,
        application_name=application_name,
    )


def _parse_database_url(database_url: str) -> DatabaseConfig:
    """
    Parse DATABASE_URL connection string.

    Format: postgresql://user:password@host:port/database

    Args:
        database_url: Connection string

    Returns:
        DatabaseConfig object
    """
    import urllib.parse

    parsed = urllib.parse.urlparse(database_url)

    if parsed.scheme not in ["postgres", "postgresql"]:
        raise ValueError(
            f"Invalid DATABASE_URL scheme: {parsed.scheme}. "
            f"Expected 'postgresql://' or 'postgres://'"
        )

    return DatabaseConfig(
        database=parsed.path.lstrip("/"),
        password=parsed.password or "",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        ssl_mode=os.getenv("DB_SSL_MODE", "require"),
        ssl_verify=_parse_bool(os.getenv("SSL_VERIFY"), True),
    )


def _load_monitor_config(file_config: Dict[str, Any]) -> MonitorConfig:
    """
    Load monitor configuration with environment variable priority.

    Args:
        file_config: Monitor section from config file

    Returns:
        MonitorConfig object
    """
    check_interval = int(
        os.getenv("DB_CHECK_INTERVAL", file_config.get("check_interval", 60))
    )
    max_retries = int(os.getenv("DB_MAX_RETRIES", file_config.get("max_retries", 3)))
    retry_backoff = os.getenv("DB_RETRY_BACKOFF") or file_config.get(
        "retry_backoff", "exponential"
    )
    retry_delay = int(os.getenv("DB_RETRY_DELAY", file_config.get("retry_delay", 5)))
    retry_jitter = _parse_bool(
        os.getenv("DB_RETRY_JITTER"), file_config.get("retry_jitter", True)
    )
    health_check_query = file_config.get(
        "health_check_query", "SELECT 1 AS health_check"
    )
    read_only_mode = _parse_bool(
        os.getenv("DB_READ_ONLY_MODE"), file_config.get("read_only_mode", True)
    )

    return MonitorConfig(
        check_interval=check_interval,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        retry_delay=retry_delay,
        retry_jitter=retry_jitter,
        health_check_query=health_check_query,
        read_only_mode=read_only_mode,
    )


def _load_logging_config(file_config: Dict[str, Any]) -> LoggingConfig:
    """
    Load logging configuration with environment variable priority.

    Args:
        file_config: Logging section from config file

    Returns:
        LoggingConfig object
    """
    level = os.getenv("DB_LOG_LEVEL") or file_config.get("level", "INFO")
    output = os.getenv("DB_LOG_OUTPUT") or file_config.get("output", "console")
    file_path = os.getenv("DB_LOG_FILE") or file_config.get(
        "file_path", "logs/db-up.log"
    )
    max_file_size = int(
        os.getenv("DB_LOG_MAX_SIZE", file_config.get("max_file_size", 10485760))
    )
    backup_count = int(
        os.getenv("DB_LOG_BACKUP_COUNT", file_config.get("backup_count", 5))
    )
    format_type = os.getenv("DB_LOG_FORMAT") or file_config.get("format", "text")
    redact_credentials = _parse_bool(
        os.getenv("DB_LOG_REDACT_CREDENTIALS"),
        file_config.get("redact_credentials", True),
    )
    redact_hostnames = _parse_bool(
        os.getenv("DB_LOG_REDACT_HOSTNAMES"), file_config.get("redact_hostnames", False)
    )

    return LoggingConfig(
        level=level,
        output=output,
        file_path=file_path,
        max_file_size=max_file_size,
        backup_count=backup_count,
        format=format_type,
        redact_credentials=redact_credentials,
        redact_hostnames=redact_hostnames,
    )


def _load_metrics_config(file_config: Dict[str, Any]) -> MetricsConfig:
    """
    Load metrics configuration with environment variable priority.

    Args:
        file_config: Metrics section from config file

    Returns:
        MetricsConfig object
    """
    enabled = _parse_bool(
        os.getenv("DB_METRICS_ENABLED"), file_config.get("enabled", False)
    )
    port = int(os.getenv("DB_METRICS_PORT", file_config.get("port", 9090)))
    host = os.getenv("DB_METRICS_HOST") or file_config.get("host", "0.0.0.0")

    return MetricsConfig(
        enabled=enabled,
        port=port,
        host=host,
    )


def _parse_bool(env_value: Optional[str], default: bool) -> bool:
    """
    Parse boolean value from environment variable or use default.

    Args:
        env_value: Environment variable value (string or None)
        default: Default value if env_value is None

    Returns:
        Boolean value
    """
    if env_value is None:
        return default

    return env_value.lower() in ("true", "1", "yes", "on")
