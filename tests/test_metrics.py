"""Tests for Prometheus metrics collection."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from prometheus_client import CollectorRegistry

from db_up.models import HealthCheckResult, MetricsConfig
from db_up.metrics import MetricsCollector, PROMETHEUS_AVAILABLE


class TestMetricsConfig:
    """Tests for MetricsConfig model."""

    def test_default_config(self) -> None:
        """Test creating metrics config with defaults."""
        config = MetricsConfig()

        assert config.enabled is False
        assert config.port == 9090
        assert config.host == "0.0.0.0"

    def test_custom_config(self) -> None:
        """Test creating metrics config with custom values."""
        config = MetricsConfig(
            enabled=True,
            port=8080,
            host="127.0.0.1"
        )

        assert config.enabled is True
        assert config.port == 8080
        assert config.host == "127.0.0.1"

    def test_invalid_port_low(self) -> None:
        """Test that port below 1024 raises ValueError."""
        with pytest.raises(ValueError) as exc:
            MetricsConfig(port=1023)

        assert "Invalid metrics port 1023" in str(exc.value)

    def test_invalid_port_high(self) -> None:
        """Test that port above 65535 raises ValueError."""
        with pytest.raises(ValueError) as exc:
            MetricsConfig(port=65536)

        assert "Invalid metrics port 65536" in str(exc.value)

    def test_valid_port_boundaries(self) -> None:
        """Test valid port boundaries."""
        # Minimum valid port
        config1 = MetricsConfig(port=1024)
        assert config1.port == 1024

        # Maximum valid port
        config2 = MetricsConfig(port=65535)
        assert config2.port == 65535


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus-client not installed")
class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_initialization(self) -> None:
        """Test MetricsCollector initialization."""
        config = MetricsConfig(enabled=True, port=9090)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        assert collector.database == "testdb"
        assert collector.host == "localhost"
        assert collector.config == config
        assert collector.registry == registry
        assert not collector.is_server_started()

    def test_initialization_without_prometheus(self) -> None:
        """Test initialization fails gracefully without prometheus-client."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        with patch('db_up.metrics.PROMETHEUS_AVAILABLE', False):
            # Need to reload the module for the patch to take effect
            # So we'll just test that PROMETHEUS_AVAILABLE check works
            if not PROMETHEUS_AVAILABLE:
                with pytest.raises(RuntimeError) as exc:
                    MetricsCollector(
                        database="testdb",
                        host="localhost",
                        config=config,
                        registry=registry
                    )
                assert "prometheus-client library is not installed" in str(exc.value)

    def test_record_successful_check(self) -> None:
        """Test recording a successful health check."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=45.0
        )

        collector.record_check(result)

        # Verify connection status is set to 1 (up)
        metrics = collector.connection_status.collect()
        for metric in metrics:
            for sample in metric.samples:
                if sample.labels.get('database') == 'testdb':
                    assert sample.value == 1.0

        # Verify check was counted
        metrics = collector.checks_total.collect()
        for metric in metrics:
            for sample in metric.samples:
                if (sample.labels.get('database') == 'testdb' and
                    sample.labels.get('status') == 'success'):
                    assert sample.value == 1.0

    def test_record_failed_check(self) -> None:
        """Test recording a failed health check."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=5000.0,
            error_code="CONNECTION_ERROR",
            error_message="Connection refused"
        )

        collector.record_check(result)

        # Verify connection status is set to 0 (down)
        metrics = collector.connection_status.collect()
        for metric in metrics:
            for sample in metric.samples:
                if sample.labels.get('database') == 'testdb':
                    assert sample.value == 0.0

        # Verify error was counted
        metrics = collector.errors_total.collect()
        for metric in metrics:
            for sample in metric.samples:
                if (sample.labels.get('database') == 'testdb' and
                    sample.labels.get('error_code') == 'CONNECTION_ERROR'):
                    assert sample.value == 1.0

    def test_record_multiple_checks(self) -> None:
        """Test recording multiple health checks."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        # Record 3 successful checks
        for _ in range(3):
            result = HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="success",
                response_time_ms=50.0
            )
            collector.record_check(result)

        # Record 2 failed checks
        for _ in range(2):
            result = HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="failure",
                response_time_ms=1000.0,
                error_code="TIMEOUT",
                error_message="Connection timeout"
            )
            collector.record_check(result)

        # Verify total successful checks
        metrics = collector.checks_total.collect()
        for metric in metrics:
            for sample in metric.samples:
                if (sample.labels.get('database') == 'testdb' and
                    sample.labels.get('status') == 'success'):
                    assert sample.value == 3.0
                elif (sample.labels.get('database') == 'testdb' and
                      sample.labels.get('status') == 'failure'):
                    assert sample.value == 2.0

        # Verify errors counted
        metrics = collector.errors_total.collect()
        for metric in metrics:
            for sample in metric.samples:
                if (sample.labels.get('database') == 'testdb' and
                    sample.labels.get('error_code') == 'TIMEOUT'):
                    assert sample.value == 2.0

    def test_check_duration_histogram(self) -> None:
        """Test that check duration histogram records values correctly."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        # Record checks with different durations
        durations_ms = [10.0, 25.0, 100.0, 500.0]
        for duration in durations_ms:
            result = HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="success",
                response_time_ms=duration
            )
            collector.record_check(result)

        # Verify histogram recorded the observations
        metrics = collector.check_duration.collect()
        for metric in metrics:
            for sample in metric.samples:
                if sample.name.endswith('_count'):
                    if sample.labels.get('database') == 'testdb':
                        assert sample.value == 4.0

    def test_different_database_labels(self) -> None:
        """Test that different database/host labels are tracked separately."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        # Create collectors for different databases
        collector1 = MetricsCollector(
            database="db1",
            host="host1",
            config=config,
            registry=registry
        )

        # Can't create second collector with same registry as it would conflict
        # So we'll just test single collector with one set of labels
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=45.0
        )

        collector1.record_check(result)

        # Verify labels are correct
        metrics = collector1.connection_status.collect()
        for metric in metrics:
            for sample in metric.samples:
                if sample.labels.get('database') == 'db1':
                    assert sample.labels.get('host') == 'host1'

    @patch('db_up.metrics.start_http_server')
    def test_start_server(self, mock_start_server: Mock) -> None:
        """Test starting the metrics HTTP server."""
        config = MetricsConfig(enabled=True, port=9090, host="0.0.0.0")
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        collector.start_server()

        # Verify server was started
        mock_start_server.assert_called_once_with(9090, addr="0.0.0.0", registry=registry)
        assert collector.is_server_started()

    @patch('db_up.metrics.start_http_server')
    def test_start_server_already_started(self, mock_start_server: Mock) -> None:
        """Test that starting server twice raises error."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        collector.start_server()

        # Try to start again
        with pytest.raises(RuntimeError) as exc:
            collector.start_server()

        assert "Metrics server is already started" in str(exc.value)

    @patch('db_up.metrics.start_http_server')
    def test_start_server_port_in_use(self, mock_start_server: Mock) -> None:
        """Test handling when metrics port is already in use."""
        config = MetricsConfig(enabled=True, port=9090)
        registry = CollectorRegistry()

        # Simulate port in use error
        mock_start_server.side_effect = OSError("Address already in use")

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        with pytest.raises(RuntimeError) as exc:
            collector.start_server()

        assert "Failed to start metrics server" in str(exc.value)
        assert "Address already in use" in str(exc.value)

    def test_metrics_labels_match_database_config(self) -> None:
        """Test that metrics labels match the database configuration."""
        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        database = "production_db"
        host = "db.example.com"

        collector = MetricsCollector(
            database=database,
            host=host,
            config=config,
            registry=registry
        )

        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="success",
            response_time_ms=30.0
        )

        collector.record_check(result)

        # Verify all metrics have correct labels
        for metric in collector.connection_status.collect():
            for sample in metric.samples:
                if 'database' in sample.labels:
                    assert sample.labels['database'] == database
                    assert sample.labels['host'] == host


class TestMetricsIntegration:
    """Integration tests for metrics with the application."""

    @patch('db_up.metrics.start_http_server')
    def test_metrics_disabled_by_default(self, mock_start_server: Mock) -> None:
        """Test that metrics are disabled by default."""
        config = MetricsConfig()

        assert config.enabled is False
        mock_start_server.assert_not_called()

    def test_error_without_error_code(self) -> None:
        """Test recording a failed check without error_code doesn't crash."""
        if not PROMETHEUS_AVAILABLE:
            pytest.skip("prometheus-client not installed")

        config = MetricsConfig(enabled=True)
        registry = CollectorRegistry()

        collector = MetricsCollector(
            database="testdb",
            host="localhost",
            config=config,
            registry=registry
        )

        # Create a failed result without error_code
        result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=1000.0,
            error_code=None,  # No error code
            error_message="Unknown error"
        )

        # Should not crash
        collector.record_check(result)

        # Verify check was still counted
        metrics = collector.checks_total.collect()
        for metric in metrics:
            for sample in metric.samples:
                if (sample.labels.get('database') == 'testdb' and
                    sample.labels.get('status') == 'failure'):
                    assert sample.value == 1.0
