"""Tests for database checker module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import psycopg2
from db_up.db_checker import DatabaseChecker, create_checker
from db_up.models import DatabaseConfig


class TestDatabaseChecker:
    """Tests for DatabaseChecker class."""
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_successful_health_check(self, mock_connect) -> None:
        """Test successful health check returns correct result."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Create checker
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        # Execute
        result = checker.check_connection()
        
        # Assert
        assert result.is_success()
        assert result.status == "success"
        assert result.response_time_ms >= 0  # Can be 0 in fast tests
        assert result.error_code is None
        
        # Verify security settings were applied
        calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('READ ONLY' in str(call) for call in calls)
        assert any('statement_timeout' in str(call) for call in calls)
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_connection_refused(self, mock_connect) -> None:
        """Test connection refused error is handled correctly."""
        mock_connect.side_effect = psycopg2.OperationalError("connection refused")
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.status == "failure"
        assert result.error_code == "CONNECTION_ERROR"
        assert "refused" in result.error_message.lower()
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_authentication_error(self, mock_connect) -> None:
        """Test authentication error is classified correctly."""
        mock_connect.side_effect = psycopg2.DatabaseError("authentication failed")
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.error_code == "AUTHENTICATION_ERROR"
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_database_not_found(self, mock_connect) -> None:
        """Test database not found error is classified correctly."""
        mock_connect.side_effect = psycopg2.DatabaseError('database "testdb" does not exist')
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.error_code == "DATABASE_NOT_FOUND"
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_too_many_connections(self, mock_connect) -> None:
        """Test too many connections error is classified correctly."""
        mock_connect.side_effect = psycopg2.DatabaseError("too many connections")
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.error_code == "TOO_MANY_CONNECTIONS"
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_query_timeout(self, mock_connect) -> None:
        """Test query timeout error is classified correctly."""
        mock_connect.side_effect = psycopg2.DatabaseError("canceling statement due to statement timeout")
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.error_code == "QUERY_TIMEOUT"
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_unexpected_error(self, mock_connect) -> None:
        """Test unexpected error is handled gracefully."""
        mock_connect.side_effect = RuntimeError("unexpected error")
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.error_code == "UNKNOWN_ERROR"
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_connection_cleanup_on_success(self, mock_connect) -> None:
        """Test that connections are cleaned up on success."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        # Verify cleanup was called
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_connection_cleanup_on_error(self, mock_connect) -> None:
        """SECURITY: Test that connections are cleaned up even on error."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.DatabaseError("error")
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        # Verify cleanup was attempted
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_password_not_in_error_message(self, mock_connect) -> None:
        """SECURITY: Test that passwords are never in error messages."""
        mock_connect.side_effect = psycopg2.OperationalError(
            "connection failed: password=secret123"
        )
        
        config = DatabaseConfig(database="testdb", password="secret123")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        # Password should not be in error message
        assert "secret123" not in result.error_message
        assert "***" in result.error_message
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_timer_injection_for_testing(self, mock_connect) -> None:
        """Test that timer can be injected for deterministic testing."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Inject mock timer
        mock_timer = Mock(side_effect=[0.0, 0.045])  # 45ms elapsed
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config, timer=mock_timer)
        
        result = checker.check_connection()
        
        assert result.response_time_ms == 45.0
        assert mock_timer.call_count == 2
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_connection_parameters(self, mock_connect) -> None:
        """Test that connection parameters are passed correctly."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        config = DatabaseConfig(
            database="testdb",
            password="secret",
            host="testhost",
            port=5433,
            user="testuser",
            ssl_mode="verify-full",
            connect_timeout=10,
            application_name="test-app"
        )
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        # Verify connection was called with correct parameters
        mock_connect.assert_called_once_with(
            host="testhost",
            port=5433,
            database="testdb",
            user="testuser",
            password="secret",
            connect_timeout=10,
            sslmode="verify-full",
            application_name="test-app",
        )
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_unexpected_query_result(self, mock_connect) -> None:
        """Test that unexpected query result is handled."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)  # Wrong result
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
        assert result.error_code == "UNKNOWN_ERROR"
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_null_query_result(self, mock_connect) -> None:
        """Test that null query result is handled."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        result = checker.check_connection()
        
        assert not result.is_success()
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_redact_hostnames_when_enabled(self, mock_connect) -> None:
        """Test that hostnames are redacted when enabled."""
        mock_connect.side_effect = psycopg2.OperationalError(
            "connection to 192.168.1.100 failed"
        )
        
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config, redact_hostnames=True)
        
        result = checker.check_connection()
        
        # IP address should be redacted
        assert "192.168.1.100" not in result.error_message
        assert "***" in result.error_message


class TestCreateChecker:
    """Tests for create_checker factory function."""
    
    def test_create_checker_returns_instance(self) -> None:
        """Test that create_checker returns a DatabaseChecker instance."""
        config = DatabaseConfig(database="testdb", password="secret")
        checker = create_checker(config)
        
        assert isinstance(checker, DatabaseChecker)
        assert checker.config == config


class TestErrorClassification:
    """Tests for error classification logic."""
    
    def test_classify_authentication_error(self) -> None:
        """Test authentication error classification."""
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        error = psycopg2.DatabaseError("authentication failed for user")
        code = checker._classify_database_error(error)
        
        assert code == "AUTHENTICATION_ERROR"
    
    def test_classify_permission_error(self) -> None:
        """Test permission error classification."""
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        error = psycopg2.DatabaseError("permission denied for database")
        code = checker._classify_database_error(error)
        
        assert code == "PERMISSION_ERROR"
    
    def test_classify_generic_database_error(self) -> None:
        """Test generic database error classification."""
        config = DatabaseConfig(database="testdb", password="secret")
        checker = DatabaseChecker(config)
        
        error = psycopg2.DatabaseError("some other error")
        code = checker._classify_database_error(error)
        
        assert code == "DATABASE_ERROR"


class TestIntegration:
    """Integration tests for database checker."""
    
    @patch('db_up.db_checker.psycopg2.connect')
    def test_complete_health_check_flow(self, mock_connect) -> None:
        """Test complete health check flow from start to finish."""
        # Setup realistic mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Create checker with full config
        config = DatabaseConfig(
            database="proddb",
            password="prodsecret",
            host="prod.example.com",
            port=5432,
            user="monitor",
            ssl_mode="require",
            connect_timeout=5,
            statement_timeout=5,
            application_name="db-up"
        )
        checker = DatabaseChecker(config)
        
        # Execute health check
        result = checker.check_connection()
        
        # Verify result
        assert result.is_success()
        assert result.response_time_ms > 0
        assert result.timestamp is not None
        
        # Verify security measures were applied
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert len(execute_calls) >= 3  # READ ONLY, timeout, SELECT 1
        
        # Verify cleanup
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

