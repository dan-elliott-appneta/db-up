"""
Tests for Prometheus metrics collection.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from db_up.models import HealthCheckResult, MetricsConfig
from db_up.metrics import MetricsCollector


class TestMetricsConfig:
    """Tests for MetricsConfig model."""

    def test_default_values(self) -> None:
        """Test MetricsConfig default values."""
        config = MetricsConfig()
        assert config.enabled is False
        assert config.port == 9090
        assert config.host == "0.0.0.0"

    def test_custom_values(self) -> None:
        """Test MetricsConfig with custom values."""
        config = MetricsConfig(enabled=True, port=8080, host="127.0.0.1")
        assert config.enabled is True
        assert config.port == 8080
        assert config.host == "127.0.0.1"

    def test_invalid_port_too_low(self) -> None:
        """Test MetricsConfig rejects port < 1."""
        with pytest.raises(ValueError, match="Invalid port 0"):
            MetricsConfig(port=0)

    def test_invalid_port_too_high(self) -> None:
        """Test MetricsConfig rejects port > 65535."""
        with pytest.raises(ValueError, match="Invalid port 70000"):
            MetricsConfig(port=70000)

    def test_valid_port_boundaries(self) -> None:
        """Test MetricsConfig accepts valid port boundaries."""
        config_min = MetricsConfig(port=1)
        assert config_min.port == 1

        config_max = MetricsConfig(port=65535)
        assert config_max.port == 65535


class TestMetricsCollectorWithPrometheus:
    """Tests for MetricsCollector when prometheus-client is available."""

    @pytest.fixture
    def mock_prometheus(self) -> Mock:
        """Mock prometheus_client module."""
        mock_counter = MagicMock()
        mock_gauge = MagicMock()
        mock_histogram = MagicMock()
        mock_start_http_server = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "prometheus_client": MagicMock(
                    Counter=mock_counter,
                    Gauge=mock_gauge,
                    Histogram=mock_histogram,
                    start_http_server=mock_start_http_server,
                )
            },
        ):
            yield {
                "Counter": mock_counter,
                "Gauge": mock_gauge,
                "Histogram": mock_histogram,
                "start_http_server": mock_start_http_server,
            }

    def test_initialization(self, mock_prometheus: Mock) -> None:
        """Test MetricsCollector initialization with prometheus-client."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        assert collector.database == "testdb"
        assert collector.host == "localhost"
        assert collector.port == 9090
        assert collector.metrics_host == "0.0.0.0"
        assert collector._prometheus_available is True
        assert collector._server_started is False

    def test_custom_metrics_host(self, mock_prometheus: Mock) -> None:
        """Test MetricsCollector with custom metrics host."""
        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            port=9090,
            metrics_host="127.0.0.1",
        )

        assert collector.metrics_host == "127.0.0.1"

    def test_start_server(self, mock_prometheus: Mock) -> None:
        """Test starting the metrics HTTP server."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        collector.start_server()

        mock_prometheus["start_http_server"].assert_called_once_with(
            9090, addr="0.0.0.0"
        )
        assert collector._server_started is True

    def test_start_server_already_started(
        self, mock_prometheus: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test starting server when already started logs warning."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        collector.start_server()
        collector.start_server()  # Try to start again

        # Should only be called once
        assert mock_prometheus["start_http_server"].call_count == 1
        assert "already started" in caplog.text.lower()

    def test_start_server_port_in_use(self, mock_prometheus: Mock) -> None:
        """Test starting server when port is already in use."""
        mock_prometheus["start_http_server"].side_effect = OSError(
            "Address already in use"
        )

        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        with pytest.raises(OSError, match="Port 9090 already in use"):
            collector.start_server()

    def test_record_successful_check(self, mock_prometheus: Mock) -> None:
        """Test recording a successful health check."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        # Create mock metric objects
        mock_connection_status = MagicMock()
        mock_check_duration = MagicMock()
        mock_checks_total = MagicMock()
        mock_errors_total = MagicMock()

        collector._connection_status = mock_connection_status
        collector._check_duration = mock_check_duration
        collector._checks_total = mock_checks_total
        collector._errors_total = mock_errors_total

        # Create a successful health check result
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=25.5,
        )

        collector.record_check(result)

        # Verify metrics were updated
        labels = {"database": "testdb", "host": "localhost"}
        mock_connection_status.labels.assert_called_with(**labels)
        mock_connection_status.labels.return_value.set.assert_called_with(1)

        mock_check_duration.labels.assert_called_with(**labels)
        mock_check_duration.labels.return_value.observe.assert_called_with(0.0255)

        mock_checks_total.labels.assert_called_with(**labels, status="success")
        mock_checks_total.labels.return_value.inc.assert_called_once()

        # Errors should not be recorded for successful checks
        mock_errors_total.labels.assert_not_called()

    def test_record_failed_check(self, mock_prometheus: Mock) -> None:
        """Test recording a failed health check."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        # Create mock metric objects
        mock_connection_status = MagicMock()
        mock_check_duration = MagicMock()
        mock_checks_total = MagicMock()
        mock_errors_total = MagicMock()

        collector._connection_status = mock_connection_status
        collector._check_duration = mock_check_duration
        collector._checks_total = mock_checks_total
        collector._errors_total = mock_errors_total

        # Create a failed health check result
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=100.0,
            error_code="CONNECTION_ERROR",
            error_message="Connection refused",
        )

        collector.record_check(result)

        # Verify metrics were updated
        labels = {"database": "testdb", "host": "localhost"}
        mock_connection_status.labels.assert_called_with(**labels)
        mock_connection_status.labels.return_value.set.assert_called_with(0)

        mock_check_duration.labels.assert_called_with(**labels)
        mock_check_duration.labels.return_value.observe.assert_called_with(0.1)

        mock_checks_total.labels.assert_called_with(**labels, status="failure")
        mock_checks_total.labels.return_value.inc.assert_called_once()

        # Errors should be recorded
        mock_errors_total.labels.assert_called_with(
            **labels, error_code="CONNECTION_ERROR"
        )
        mock_errors_total.labels.return_value.inc.assert_called_once()

    def test_record_multiple_checks(self, mock_prometheus: Mock) -> None:
        """Test recording multiple health checks accumulates metrics."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        # Create mock metric objects
        mock_connection_status = MagicMock()
        mock_check_duration = MagicMock()
        mock_checks_total = MagicMock()
        mock_errors_total = MagicMock()

        collector._connection_status = mock_connection_status
        collector._check_duration = mock_check_duration
        collector._checks_total = mock_checks_total
        collector._errors_total = mock_errors_total

        # Record 3 successful checks
        for i in range(3):
            result = HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="success",
                response_time_ms=10.0 * (i + 1),
            )
            collector.record_check(result)

        # Verify counters were incremented 3 times
        assert mock_checks_total.labels.return_value.inc.call_count == 3
        assert mock_check_duration.labels.return_value.observe.call_count == 3

    def test_record_check_different_durations(
        self, mock_prometheus: Mock
    ) -> None:
        """Test recording checks with different response times."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        mock_check_duration = MagicMock()
        collector._check_duration = mock_check_duration
        collector._connection_status = MagicMock()
        collector._checks_total = MagicMock()
        collector._errors_total = MagicMock()

        # Test various response times
        durations_ms = [1.5, 15.0, 150.0, 1500.0]
        expected_seconds = [0.0015, 0.015, 0.15, 1.5]

        for duration_ms, expected_sec in zip(durations_ms, expected_seconds):
            result = HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="success",
                response_time_ms=duration_ms,
            )
            collector.record_check(result)

            # Get the most recent call
            calls = mock_check_duration.labels.return_value.observe.call_args_list
            assert calls[-1][0][0] == expected_sec

    def test_record_failed_check_without_error_code(
        self, mock_prometheus: Mock
    ) -> None:
        """Test recording failed check without error code."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )

        mock_connection_status = MagicMock()
        mock_check_duration = MagicMock()
        mock_checks_total = MagicMock()
        mock_errors_total = MagicMock()

        collector._connection_status = mock_connection_status
        collector._check_duration = mock_check_duration
        collector._checks_total = mock_checks_total
        collector._errors_total = mock_errors_total

        # Create a failed check without error code
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=50.0,
            error_code=None,
            error_message="Unknown error",
        )

        collector.record_check(result)

        # Error metric should not be recorded when error_code is None
        mock_errors_total.labels.assert_not_called()

    def test_database_labels(self, mock_prometheus: Mock) -> None:
        """Test that database and host labels are correctly set."""
        collector = MetricsCollector(
            database="production_db",
            host="db.example.com",
            port=9090,
        )

        mock_connection_status = MagicMock()
        collector._connection_status = mock_connection_status
        collector._check_duration = MagicMock()
        collector._checks_total = MagicMock()
        collector._errors_total = MagicMock()

        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=10.0,
        )

        collector.record_check(result)

        # Verify correct labels were used
        expected_labels = {"database": "production_db", "host": "db.example.com"}
        mock_connection_status.labels.assert_called_with(**expected_labels)


class TestMetricsCollectorWithoutPrometheus:
    """Tests for MetricsCollector when prometheus-client is not available."""

    @pytest.fixture
    def mock_prometheus(self) -> Mock:
        """Mock prometheus_client module for creating collector."""
        mock_counter = MagicMock()
        mock_gauge = MagicMock()
        mock_histogram = MagicMock()
        mock_start_http_server = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "prometheus_client": MagicMock(
                    Counter=mock_counter,
                    Gauge=mock_gauge,
                    Histogram=mock_histogram,
                    start_http_server=mock_start_http_server,
                )
            },
        ):
            yield {
                "Counter": mock_counter,
                "Gauge": mock_gauge,
                "Histogram": mock_histogram,
                "start_http_server": mock_start_http_server,
            }

    def test_initialization_without_prometheus(
        self, mock_prometheus: Mock
    ) -> None:
        """Test MetricsCollector behavior when prometheus is disabled."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )
        # Simulate prometheus not available
        collector._prometheus_available = False

        assert collector._prometheus_available is False
        assert collector.database == "testdb"
        assert collector.host == "localhost"

    def test_start_server_without_prometheus(
        self, mock_prometheus: Mock
    ) -> None:
        """Test starting server when prometheus-client is not available."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )
        collector._prometheus_available = False

        with pytest.raises(
            RuntimeError, match="prometheus-client not installed"
        ):
            collector.start_server()

    def test_record_check_without_prometheus(
        self, mock_prometheus: Mock
    ) -> None:
        """Test recording check when prometheus-client is not available."""
        collector = MetricsCollector(
            database="testdb", host="localhost", port=9090
        )
        collector._prometheus_available = False

        # Should not raise error, just return early
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=10.0,
        )

        # Should complete without error
        collector.record_check(result)
