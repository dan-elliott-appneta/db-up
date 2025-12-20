"""
Prometheus metrics for db-up.

This module provides Prometheus metrics collection and exposure for
database monitoring including:
- Connection status
- Check duration
- Check counts by status
- Error counts by error code
"""

from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import logging

from db_up.models import HealthCheckResult


# Define Prometheus metrics
connection_status = Gauge(
    'db_up_connection_status',
    'Current database connection status (1=up, 0=down)',
    ['database', 'host']
)

check_duration = Histogram(
    'db_up_check_duration_seconds',
    'Time taken for database health checks',
    ['database', 'host'],
    buckets=[.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0]
)

checks_total = Counter(
    'db_up_checks_total',
    'Total number of database health checks',
    ['database', 'host', 'status']
)

errors_total = Counter(
    'db_up_errors_total',
    'Total number of database errors',
    ['database', 'host', 'error_code']
)


class MetricsCollector:
    """
    Metrics collector for database health checks.

    This class records health check results as Prometheus metrics
    and can optionally run an HTTP server to expose the /metrics endpoint.
    """

    def __init__(
        self,
        database_name: str,
        database_host: str,
        enabled: bool = True,
        port: Optional[int] = None
    ):
        """
        Initialize the metrics collector.

        Args:
            database_name: Name of the database being monitored
            database_host: Hostname of the database being monitored
            enabled: Whether metrics collection is enabled
            port: Port for the metrics HTTP server (if None, server won't start)
        """
        self.database_name = database_name
        self.database_host = database_host
        self.enabled = enabled
        self.port = port
        self.server_started = False
        self.logger = logging.getLogger(__name__)

        if self.enabled and self.port:
            self._start_metrics_server()

    def _start_metrics_server(self) -> None:
        """
        Start the Prometheus metrics HTTP server.

        This starts a simple HTTP server that exposes metrics at /metrics.
        The server runs in a separate thread.
        """
        if self.server_started:
            return

        try:
            start_http_server(self.port)
            self.server_started = True
            self.logger.info(f"Prometheus metrics server started on port {self.port}")
            self.logger.info(f"Metrics available at http://localhost:{self.port}/metrics")
        except OSError as e:
            self.logger.error(f"Failed to start metrics server on port {self.port}: {e}")
            self.enabled = False

    def record_check_result(self, result: HealthCheckResult) -> None:
        """
        Record a health check result as Prometheus metrics.

        This updates:
        - Connection status gauge
        - Check duration histogram
        - Check counter
        - Error counter (if applicable)

        Args:
            result: Health check result to record
        """
        if not self.enabled:
            return

        labels = {
            'database': self.database_name,
            'host': self.database_host
        }

        # Record connection status
        status_value = 1 if result.is_success() else 0
        connection_status.labels(**labels).set(status_value)

        # Record check duration (convert ms to seconds)
        duration_seconds = result.response_time_ms / 1000.0
        check_duration.labels(**labels).observe(duration_seconds)

        # Record check count
        checks_total.labels(**labels, status=result.status).inc()

        # Record errors if applicable
        if not result.is_success() and result.error_code:
            errors_total.labels(**labels, error_code=result.error_code).inc()

    def shutdown(self) -> None:
        """
        Shutdown the metrics collector.

        Note: The prometheus_client HTTP server doesn't provide a clean
        shutdown mechanism, so this method is primarily a placeholder
        for future cleanup logic.
        """
        if self.server_started:
            self.logger.info("Metrics collector shutting down")
