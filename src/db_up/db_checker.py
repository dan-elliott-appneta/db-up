"""
Database connectivity checker for db-up.

This module provides the core database health check functionality with:
- Dependency injection for testability
- Read-only transaction mode for security
- Statement timeout for safety
- Comprehensive error handling
- Automatic credential sanitization

SECURITY: All database operations use read-only mode and have timeouts.
"""

import time
from datetime import datetime
from typing import Optional, Callable
import psycopg2
from psycopg2 import sql

from db_up.models import DatabaseConfig, HealthCheckResult
from db_up.security import sanitize_error


class DatabaseChecker:
    """
    Database connectivity checker with dependency injection.

    This class performs health checks on PostgreSQL databases with
    security best practices:
    - Read-only transaction mode
    - Statement timeout
    - Automatic credential sanitization
    - Guaranteed connection cleanup

    The timer can be injected for deterministic testing.
    """

    def __init__(
        self,
        config: DatabaseConfig,
        timer: Optional[Callable[[], float]] = None,
        redact_hostnames: bool = False,
    ):
        """
        Initialize the database checker.

        Args:
            config: Database configuration
            timer: Optional timer function for testing (default: time.time)
            redact_hostnames: If True, redact IP addresses in errors
        """
        self.config = config
        self.timer = timer or time.time
        self.redact_hostnames = redact_hostnames

    def check_connection(self) -> HealthCheckResult:
        """
        Perform a database health check.

        This method:
        1. Establishes a connection with timeout
        2. Sets read-only transaction mode (SECURITY)
        3. Sets statement timeout (SECURITY)
        4. Executes health check query
        5. Verifies result
        6. Measures response time
        7. Guarantees connection cleanup

        Returns:
            HealthCheckResult with status and timing

        Example:
            >>> config = DatabaseConfig(database="mydb", password="secret")
            >>> checker = DatabaseChecker(config)
            >>> result = checker.check_connection()
            >>> if result.is_success():
            ...     print(f"Database is up! Response time: {result.response_time_ms}ms")
        """
        start_time = self.timer()
        conn = None
        cursor = None

        try:
            # Establish connection with security settings
            # Build connection parameters
            conn_params = {
                "host": self.config.host,
                "port": self.config.port,
                "database": self.config.database,
                "user": self.config.user,
                "password": self.config.password,
                "connect_timeout": self.config.connect_timeout,
                "sslmode": self.config.ssl_mode,
                "application_name": self.config.application_name,
            }

            # Add SSL verification parameter if disabled
            if not self.config.ssl_verify:
                # When SSL_VERIFY is false, we need to disable certificate verification
                # by using sslmode 'require' which requires SSL but doesn't verify cert
                conn_params["sslmode"] = "require"
                if self.config.ssl_mode in ["verify-ca", "verify-full"]:
                    # Override to 'require' to skip verification
                    conn_params["sslmode"] = "require"

            conn = psycopg2.connect(**conn_params)

            cursor = conn.cursor()

            # SECURITY: Set read-only mode
            cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")

            # SECURITY: Set statement timeout
            cursor.execute(
                sql.SQL("SET statement_timeout = %s"),
                [f"{self.config.statement_timeout}s"],
            )

            # Execute health check query
            # Note: Using simple query, not parameterized, but query is validated
            cursor.execute("SELECT 1 AS health_check")
            result = cursor.fetchone()

            # Verify expected result
            if result is None or result[0] != 1:
                raise ValueError("Unexpected health check result")

            elapsed_ms = (self.timer() - start_time) * 1000

            return HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="success",
                response_time_ms=elapsed_ms,
            )

        except psycopg2.OperationalError as e:
            # Network/connection errors
            return self._handle_error(
                start_time, "CONNECTION_ERROR", self._sanitize_error(str(e))
            )

        except psycopg2.DatabaseError as e:
            # Database-specific errors (including authentication)
            error_code = self._classify_database_error(e)
            return self._handle_error(
                start_time, error_code, self._sanitize_error(str(e))
            )

        except Exception:
            # Unexpected errors
            return self._handle_error(
                start_time,
                "UNKNOWN_ERROR",
                "An unexpected error occurred during health check",
            )

        finally:
            # SECURITY: Guaranteed cleanup even on error
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _handle_error(
        self, start_time: float, error_code: str, error_message: str
    ) -> HealthCheckResult:
        """
        Create error result with sanitized message.

        Args:
            start_time: Start time of the check
            error_code: Error code
            error_message: Error message (already sanitized)

        Returns:
            HealthCheckResult with failure status
        """
        elapsed_ms = (self.timer() - start_time) * 1000
        return HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=elapsed_ms,
            error_code=error_code,
            error_message=error_message,
        )

    def _sanitize_error(self, error: str) -> str:
        """
        SECURITY: Remove sensitive information from error messages.

        Args:
            error: Raw error message

        Returns:
            Sanitized error message
        """
        return sanitize_error(error, self.redact_hostnames)

    def _classify_database_error(self, error: psycopg2.DatabaseError) -> str:
        """
        Classify database error into appropriate error code.

        Args:
            error: Database error

        Returns:
            Error code string
        """
        error_str = str(error).lower()

        # Authentication errors
        if "authentication" in error_str or "password" in error_str:
            return "AUTHENTICATION_ERROR"

        # Permission errors
        if "permission" in error_str or "access denied" in error_str:
            return "PERMISSION_ERROR"

        # Database not found
        if "database" in error_str and "does not exist" in error_str:
            return "DATABASE_NOT_FOUND"

        # Connection pool exhausted
        if "too many connections" in error_str:
            return "TOO_MANY_CONNECTIONS"

        # Query timeout
        if "timeout" in error_str or "canceling statement" in error_str:
            return "QUERY_TIMEOUT"

        # Generic database error
        return "DATABASE_ERROR"


def create_checker(config: DatabaseConfig) -> DatabaseChecker:
    """
    Factory function to create a DatabaseChecker.

    This is a convenience function for creating checkers with default settings.

    Args:
        config: Database configuration

    Returns:
        DatabaseChecker instance

    Example:
        >>> config = DatabaseConfig(database="mydb", password="secret")
        >>> checker = create_checker(config)
        >>> result = checker.check_connection()
    """
    return DatabaseChecker(config)
