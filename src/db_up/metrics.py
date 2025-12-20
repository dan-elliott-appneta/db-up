"""
Prometheus metrics collection for db-up.

This module provides Prometheus metrics export functionality for monitoring
database health check status, response times, check counts, and errors.
"""

from typing import Optional
import threading

try:
    from prometheus_client import (
        Gauge,
        Histogram,
        Counter,
        start_http_server,
        REGISTRY,
        CollectorRegistry,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from db_up.models import HealthCheckResult, MetricsConfig


class MetricsCollector:
    """
    Collects and exposes Prometheus metrics for database health monitoring.

    This class provides a thread-safe way to collect metrics about database
    health checks and expose them via HTTP for Prometheus scraping.

    Metrics exposed:
    - db_up_connection_status: Current connection status (1=up, 0=down)
    - db_up_check_duration_seconds: Histogram of health check durations
    - db_up_checks_total: Counter of total health checks by status
    - db_up_errors_total: Counter of errors by error code
    """

    def __init__(
        self,
        database: str,
        host: str,
        config: MetricsConfig,
        registry: Optional[CollectorRegistry] = None
    ):
        """
        Initialize the metrics collector.

        Args:
            database: Database name for labeling metrics
            host: Database host for labeling metrics
            config: Metrics configuration
            registry: Optional custom Prometheus registry (for testing)

        Raises:
            RuntimeError: If Prometheus client library is not installed
        """
        if not PROMETHEUS_AVAILABLE:
            raise RuntimeError(
                "prometheus-client library is not installed. "
                "Install it with: pip install prometheus-client"
            )

        self.database = database
        self.host = host
        self.config = config
        self.registry = registry or REGISTRY
        self._server_started = False
        self._lock = threading.Lock()

        # Initialize metrics
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        # Gauge for current connection status
        self.connection_status = Gauge(
            'db_up_connection_status',
            'Current database connection status (1=up, 0=down)',
            ['database', 'host'],
            registry=self.registry
        )

        # Histogram for check duration
        self.check_duration = Histogram(
            'db_up_check_duration_seconds',
            'Database health check duration in seconds',
            ['database', 'host'],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )

        # Counter for total checks by status
        self.checks_total = Counter(
            'db_up_checks_total',
            'Total number of database health checks',
            ['database', 'host', 'status'],
            registry=self.registry
        )

        # Counter for errors by error code
        self.errors_total = Counter(
            'db_up_errors_total',
            'Total number of database check errors',
            ['database', 'host', 'error_code'],
            registry=self.registry
        )

    def start_server(self) -> None:
        """
        Start the HTTP server to expose metrics.

        This starts a background HTTP server on the configured port.
        The server will expose metrics at /metrics endpoint.

        Raises:
            RuntimeError: If server is already started or port is in use
        """
        with self._lock:
            if self._server_started:
                raise RuntimeError("Metrics server is already started")

            try:
                start_http_server(self.config.port, addr=self.config.host, registry=self.registry)
                self._server_started = True
            except OSError as e:
                raise RuntimeError(
                    f"Failed to start metrics server on {self.config.host}:{self.config.port}: {e}"
                )

    def record_check(self, result: HealthCheckResult) -> None:
        """
        Record a health check result.

        This updates all relevant metrics based on the health check result.

        Args:
            result: The health check result to record
        """
        labels = {'database': self.database, 'host': self.host}

        # Update connection status
        status_value = 1.0 if result.is_success() else 0.0
        self.connection_status.labels(**labels).set(status_value)

        # Record check duration (convert ms to seconds)
        duration_seconds = result.response_time_ms / 1000.0
        self.check_duration.labels(**labels).observe(duration_seconds)

        # Increment total checks counter
        status_label = result.status
        self.checks_total.labels(database=self.database, host=self.host, status=status_label).inc()

        # Record error if check failed
        if not result.is_success() and result.error_code:
            self.errors_total.labels(
                database=self.database,
                host=self.host,
                error_code=result.error_code
            ).inc()

    def is_server_started(self) -> bool:
        """
        Check if the metrics server is running.

        Returns:
            True if server is started, False otherwise
        """
        return self._server_started
