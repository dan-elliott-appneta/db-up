"""
Prometheus metrics collection for db-up.

This module provides Prometheus metrics for monitoring database connection
status and performance.
"""

import logging
from typing import Optional

from db_up.models import HealthCheckResult

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and exposes Prometheus metrics for database monitoring.

    Metrics exposed:
    - db_up_connection_status: Gauge for current connection status (1=up, 0=down)
    - db_up_check_duration_seconds: Histogram of health check durations
    - db_up_checks_total: Counter of total checks by status
    - db_up_errors_total: Counter of errors by error code

    All metrics include labels: database, host
    """

    def __init__(
        self, database: str, host: str, port: int, metrics_host: str = "0.0.0.0"
    ) -> None:
        """
        Initialize the metrics collector.

        Args:
            database: Database name for labels
            host: Database host for labels
            port: Port for metrics HTTP server
            metrics_host: Host to bind metrics server (default: 0.0.0.0)
        """
        self.database = database
        self.host = host
        self.port = port
        self.metrics_host = metrics_host
        self._server_started = False

        try:
            from prometheus_client import Counter, Gauge, Histogram, start_http_server

            self._start_http_server = start_http_server
            self._prometheus_available = True

            # Create metrics with labels
            self._connection_status = Gauge(
                "db_up_connection_status",
                "Current database connection status (1=up, 0=down)",
                ["database", "host"],
            )

            self._check_duration = Histogram(
                "db_up_check_duration_seconds",
                "Duration of health checks in seconds",
                ["database", "host"],
                buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
            )

            self._checks_total = Counter(
                "db_up_checks_total",
                "Total number of health checks",
                ["database", "host", "status"],
            )

            self._errors_total = Counter(
                "db_up_errors_total",
                "Total number of errors by error code",
                ["database", "host", "error_code"],
            )

            logger.info(
                f"Metrics collector initialized for {database}@{host} "
                f"(metrics server will be on {metrics_host}:{port})"
            )

        except ImportError:
            self._prometheus_available = False
            logger.warning(
                "prometheus-client not installed. Metrics collection disabled. "
                "Install with: pip install prometheus-client"
            )

    def start_server(self) -> None:
        """
        Start the Prometheus metrics HTTP server.

        Raises:
            RuntimeError: If prometheus-client is not available
            OSError: If port is already in use
        """
        if not self._prometheus_available:
            raise RuntimeError(
                "prometheus-client not installed. Cannot start metrics server."
            )

        if self._server_started:
            logger.warning(
                f"Metrics server already started on {self.metrics_host}:{self.port}"
            )
            return

        try:
            self._start_http_server(self.port, addr=self.metrics_host)
            self._server_started = True
            logger.info(
                f"Metrics server started on http://{self.metrics_host}:{self.port}/metrics"
            )
        except OSError as e:
            if "Address already in use" in str(e):
                raise OSError(
                    f"Port {self.port} already in use. "
                    f"Choose a different port with DB_METRICS_PORT env var."
                ) from e
            raise

    def record_check(self, result: HealthCheckResult) -> None:
        """
        Record a health check result.

        Args:
            result: Health check result to record
        """
        if not self._prometheus_available:
            return

        labels = {"database": self.database, "host": self.host}

        # Update connection status
        status_value = 1 if result.is_success() else 0
        self._connection_status.labels(**labels).set(status_value)

        # Record check duration
        duration_seconds = result.response_time_ms / 1000.0
        self._check_duration.labels(**labels).observe(duration_seconds)

        # Increment check counter
        status_label = "success" if result.is_success() else "failure"
        self._checks_total.labels(**labels, status=status_label).inc()

        # Record errors
        if not result.is_success() and result.error_code:
            self._errors_total.labels(
                **labels, error_code=result.error_code
            ).inc()
