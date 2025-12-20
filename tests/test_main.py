"""Tests for main application module."""

import signal
from unittest.mock import Mock, patch
from db_up.main import Application, parse_args, main
from db_up.models import (
    Config,
    DatabaseConfig,
    MonitorConfig,
    LoggingConfig,
    HealthCheckResult,
)
from datetime import datetime


class TestApplication:
    """Tests for Application class."""

    def test_application_initialization(self) -> None:
        """Test that application initializes correctly."""
        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(),
            logging=LoggingConfig(),
        )

        app = Application(config)

        assert app.config == config
        assert app.running is False
        assert app.check_count == 0
        assert app.logger is not None
        assert app.checker is not None

    @patch("db_up.main.DatabaseChecker")
    def test_run_once_success(self, mock_checker_class) -> None:
        """Test run_once with successful health check."""
        # Setup mocks
        mock_checker = Mock()
        mock_result = HealthCheckResult(
            timestamp=datetime.utcnow(), status="success", response_time_ms=45.0
        )
        mock_checker.check_connection.return_value = mock_result
        mock_checker_class.return_value = mock_checker

        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(),
            logging=LoggingConfig(),
        )

        app = Application(config)
        exit_code = app.run_once()

        assert exit_code == 0
        assert mock_checker.check_connection.called

    @patch("db_up.main.DatabaseChecker")
    def test_run_once_failure(self, mock_checker_class) -> None:
        """Test run_once with failed health check."""
        # Setup mocks
        mock_checker = Mock()
        mock_result = HealthCheckResult(
            timestamp=datetime.utcnow(),
            status="failure",
            response_time_ms=5000.0,
            error_code="CONNECTION_ERROR",
            error_message="Connection refused",
        )
        mock_checker.check_connection.return_value = mock_result
        mock_checker_class.return_value = mock_checker

        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(),
            logging=LoggingConfig(),
        )

        app = Application(config)
        exit_code = app.run_once()

        assert exit_code == 1

    @patch("db_up.main.DatabaseChecker")
    @patch("db_up.main.time.sleep")
    def test_run_loop(self, mock_sleep, mock_checker_class) -> None:
        """Test main run loop executes checks."""
        # Setup mocks
        mock_checker = Mock()
        mock_result = HealthCheckResult(
            timestamp=datetime.utcnow(), status="success", response_time_ms=45.0
        )
        mock_checker.check_connection.return_value = mock_result
        mock_checker_class.return_value = mock_checker

        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(check_interval=10),
            logging=LoggingConfig(),
        )

        app = Application(config)

        # Run for a short time then stop
        def stop_after_checks(*args):
            if mock_checker.check_connection.call_count >= 3:
                app.running = False

        mock_sleep.side_effect = stop_after_checks

        app.run()

        # Should have done 3 checks
        assert mock_checker.check_connection.call_count == 3
        assert app.check_count == 3

    @patch("db_up.main.DatabaseChecker")
    @patch("db_up.main.time.sleep")
    def test_run_handles_errors(self, mock_sleep, mock_checker_class) -> None:
        """Test that run loop handles errors gracefully."""
        # Setup mocks
        mock_checker = Mock()
        mock_checker.check_connection.side_effect = [
            Exception("unexpected error"),
            HealthCheckResult(
                timestamp=datetime.utcnow(), status="success", response_time_ms=45.0
            ),
        ]
        mock_checker_class.return_value = mock_checker

        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(),
            logging=LoggingConfig(),
        )

        app = Application(config)

        # Run for 2 checks then stop
        def stop_after_checks(*args):
            if mock_checker.check_connection.call_count >= 2:
                app.running = False

        mock_sleep.side_effect = stop_after_checks

        # Should not raise exception
        app.run()

        assert app.check_count == 2

    @patch("db_up.main.DatabaseChecker")
    def test_signal_handler_stops_application(self, mock_checker_class) -> None:
        """Test that signal handler stops the application."""
        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(),
            logging=LoggingConfig(),
        )

        app = Application(config)
        app.running = True

        # Simulate SIGINT
        app._signal_handler(signal.SIGINT, None)

        assert app.running is False

    @patch("db_up.main.DatabaseChecker")
    @patch("db_up.main.time.sleep")
    def test_check_interval_respected(self, mock_sleep, mock_checker_class) -> None:
        """Test that check interval is respected."""
        mock_checker = Mock()
        mock_result = HealthCheckResult(
            timestamp=datetime.utcnow(), status="success", response_time_ms=45.0
        )
        mock_checker.check_connection.return_value = mock_result
        mock_checker_class.return_value = mock_checker

        config = Config(
            database=DatabaseConfig(database="testdb", password="secret"),
            monitor=MonitorConfig(check_interval=30),
            logging=LoggingConfig(),
        )

        app = Application(config)

        # Stop after first check
        def stop_after_first(*args):
            app.running = False

        mock_sleep.side_effect = stop_after_first

        app.run()

        # Should have slept for 30 seconds
        mock_sleep.assert_called_with(30)


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_no_args(self) -> None:
        """Test parsing with no arguments."""
        with patch("sys.argv", ["db-up"]):
            args = parse_args()

            assert args.config is None
            assert args.once is False

    def test_parse_config_arg(self) -> None:
        """Test parsing --config argument."""
        with patch("sys.argv", ["db-up", "--config", "config.yaml"]):
            args = parse_args()

            assert args.config == "config.yaml"

    def test_parse_once_arg(self) -> None:
        """Test parsing --once argument."""
        with patch("sys.argv", ["db-up", "--once"]):
            args = parse_args()

            assert args.once is True

    def test_parse_short_config_arg(self) -> None:
        """Test parsing -c short argument."""
        with patch("sys.argv", ["db-up", "-c", "config.yaml"]):
            args = parse_args()

            assert args.config == "config.yaml"


class TestMain:
    """Tests for main function."""

    @patch("db_up.main.Application")
    @patch("db_up.main.load_config")
    def test_main_success(self, mock_load_config, mock_app_class) -> None:
        """Test main function with successful execution."""
        # Setup mocks
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        mock_app = Mock()
        mock_app.run_once.return_value = 0
        mock_app_class.return_value = mock_app

        with patch("sys.argv", ["db-up", "--once"]):
            exit_code = main()

        assert exit_code == 0
        mock_load_config.assert_called_once()
        mock_app.run_once.assert_called_once()

    @patch("db_up.main.load_config")
    def test_main_config_error(self, mock_load_config) -> None:
        """Test main function with configuration error."""
        mock_load_config.side_effect = ValueError("Invalid config")

        with patch("sys.argv", ["db-up"]):
            exit_code = main()

        assert exit_code == 1

    @patch("db_up.main.Application")
    @patch("db_up.main.load_config")
    def test_main_keyboard_interrupt(self, mock_load_config, mock_app_class) -> None:
        """Test main function handles KeyboardInterrupt."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        mock_app = Mock()
        mock_app.run.side_effect = KeyboardInterrupt()
        mock_app_class.return_value = mock_app

        with patch("sys.argv", ["db-up"]):
            exit_code = main()

        assert exit_code == 130

    @patch("db_up.main.Application")
    @patch("db_up.main.load_config")
    def test_main_unexpected_error(self, mock_load_config, mock_app_class) -> None:
        """Test main function handles unexpected errors."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        mock_app = Mock()
        mock_app.run.side_effect = RuntimeError("Unexpected error")
        mock_app_class.return_value = mock_app

        with patch("sys.argv", ["db-up"]):
            exit_code = main()

        assert exit_code == 1

    @patch("db_up.main.Application")
    @patch("db_up.main.load_config")
    def test_main_with_config_file(self, mock_load_config, mock_app_class) -> None:
        """Test main function with config file argument."""
        mock_config = Mock()
        mock_load_config.return_value = mock_config

        mock_app = Mock()
        mock_app.run_once.return_value = 0
        mock_app_class.return_value = mock_app

        with patch("sys.argv", ["db-up", "--config", "test.yaml", "--once"]):
            exit_code = main()

        mock_load_config.assert_called_once_with("test.yaml")
        assert exit_code == 0


class TestIntegration:
    """Integration tests for main application."""

    @patch("db_up.main.DatabaseChecker")
    @patch("db_up.main.time.sleep")
    def test_complete_application_flow(self, mock_sleep, mock_checker_class) -> None:
        """Test complete application flow from start to finish."""
        # Setup realistic scenario
        mock_checker = Mock()
        results = [
            HealthCheckResult(
                timestamp=datetime.utcnow(), status="success", response_time_ms=45.0
            ),
            HealthCheckResult(
                timestamp=datetime.utcnow(),
                status="failure",
                response_time_ms=5000.0,
                error_code="CONNECTION_ERROR",
                error_message="Connection refused",
            ),
            HealthCheckResult(
                timestamp=datetime.utcnow(), status="success", response_time_ms=52.0
            ),
        ]
        mock_checker.check_connection.side_effect = results
        mock_checker_class.return_value = mock_checker

        config = Config(
            database=DatabaseConfig(
                database="proddb", password="secret", host="prod.example.com"
            ),
            monitor=MonitorConfig(check_interval=60),
            logging=LoggingConfig(level="INFO", output="console"),
        )

        app = Application(config)

        # Stop after 3 checks
        def stop_after_checks(*args):
            if mock_checker.check_connection.call_count >= 3:
                app.running = False

        mock_sleep.side_effect = stop_after_checks

        app.run()

        # Verify all checks were performed
        assert app.check_count == 3
        assert mock_checker.check_connection.call_count == 3
