"""
Main application entry point for db-up.

This module provides the main application loop and CLI interface.
"""

import sys
import signal
import time
import argparse
from typing import Any, Optional

from db_up.config import load_config
from db_up.logger import setup_logging
from db_up.db_checker import DatabaseChecker
from db_up.models import Config
from db_up.metrics import MetricsCollector


class Application:
    """
    Main application class for db-up.

    This class manages the application lifecycle:
    - Configuration loading
    - Logging setup
    - Database health checking
    - Graceful shutdown
    """

    def __init__(self, config: Config):
        """
        Initialize the application.

        Args:
            config: Application configuration
        """
        self.config = config
        self.running = False
        self.logger = setup_logging(config.logging)
        self.checker = DatabaseChecker(
            config.database, redact_hostnames=config.logging.redact_hostnames
        )
        self.check_count = 0

        # Initialize metrics collector if enabled
        self.metrics: Optional[MetricsCollector] = None
        if config.metrics.enabled:
            self.metrics = MetricsCollector(
                database=config.database.database,
                host=config.database.host,
                port=config.metrics.port,
                metrics_host=config.metrics.host,
                histogram_buckets=config.metrics.histogram_buckets,
            )
            if not self.metrics._prometheus_available:
                self.logger.warning(
                    "=" * 60 + "\n"
                    "METRICS DISABLED: prometheus-client not installed.\n"
                    "Install with: pip install prometheus-client\n"
                    "Or: pip install db-up[metrics]\n"
                    + "=" * 60
                )
                self.metrics = None
            else:
                try:
                    self.metrics.start_server()
                except Exception as e:
                    self.logger.error(
                        "=" * 60 + "\n"
                        f"METRICS SERVER FAILED TO START: {e}\n"
                        f"Check if port {config.metrics.port} is available.\n"
                        "Metrics collection will be disabled for this session.\n"
                        + "=" * 60
                    )
                    self.metrics = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """
        Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received {signal_name}, shutting down gracefully...")
        self.running = False

    def run_once(self) -> int:
        """
        Run a single health check.

        This is useful for testing or one-off checks.

        Returns:
            Exit code: 0 for success, 1 for failure
        """
        self.logger.info("Running single health check...")

        result = self.checker.check_connection()

        # Record metrics if enabled
        if self.metrics:
            self.metrics.record_check(result)

        if result.is_success():
            ms = result.response_time_ms
            self.logger.info(f"✓ Health check passed - Response time: {ms:.0f}ms")
            return 0
        else:
            err = f"{result.error_code}: {result.error_message}"
            self.logger.error(f"✗ Health check failed - {err}")
            return 1

    def run(self) -> None:
        """
        Run the main application loop.

        This continuously monitors the database at the configured interval
        until interrupted.
        """
        self.running = True
        db = self.config.database
        self.logger.info(
            f"Starting db-up monitor - Database: {db.database}@{db.host}:{db.port}, "
            f"Check interval: {self.config.monitor.check_interval}s"
        )

        while self.running:
            self.check_count += 1

            try:
                result = self.checker.check_connection()

                # Record metrics if enabled
                if self.metrics:
                    self.metrics.record_check(result)

                if result.is_success():
                    response_ms = result.response_time_ms
                    msg = f"Health check passed - Response time: {response_ms:.0f}ms"
                    self.logger.info(
                        msg,
                        extra={
                            "response_time_ms": result.response_time_ms,
                            "status": "success",
                            "check_number": self.check_count,
                        },
                    )
                else:
                    err = f"{result.error_code}: {result.error_message}"
                    msg = f"Health check failed - {err}"
                    self.logger.warning(
                        msg,
                        extra={
                            "response_time_ms": result.response_time_ms,
                            "status": "failure",
                            "error_code": result.error_code,
                            "error_message": result.error_message,
                            "check_number": self.check_count,
                        },
                    )

            except Exception as e:
                self.logger.error(
                    f"Unexpected error during health check: {e}", exc_info=True
                )

            # Wait for next check (if still running)
            if self.running:
                time.sleep(self.config.monitor.check_interval)

        self._shutdown()
        self.logger.info(f"Shutting down after {self.check_count} health checks")

    def _shutdown(self) -> None:
        """Clean up resources during shutdown."""
        if self.metrics:
            try:
                self.metrics.shutdown()
            except Exception as e:
                self.logger.warning(f"Error shutting down metrics server: {e}")


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="db-up: PostgreSQL database connectivity monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variables (recommended)
  export DB_NAME=mydb DB_PASSWORD=secret
  db-up

  # Using config file
  db-up --config config.yaml

  # One-time check
  db-up --once

  # Custom interval
  db-up --interval 30

For more information, visit: https://github.com/dan-elliott-appneta/db-up
        """,
    )

    parser.add_argument(
        "--config", "-c", type=str, help="Path to configuration file (YAML)"
    )

    parser.add_argument(
        "--once", action="store_true", help="Run health check once and exit"
    )

    parser.add_argument("--version", "-v", action="version", version="db-up 1.0.0")

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    try:
        # Parse command line arguments
        args = parse_args()

        # Load configuration
        try:
            config = load_config(args.config)
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            return 1

        # Create and run application
        app = Application(config)

        if args.once:
            return app.run_once()
        else:
            app.run()
            return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
