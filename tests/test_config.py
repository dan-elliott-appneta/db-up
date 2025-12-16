"""Tests for configuration loading."""

import os
import pytest
import tempfile
from pathlib import Path
from db_up.config import (
    load_config,
    _load_yaml_config,
    _load_database_config,
    _parse_database_url,
    _load_monitor_config,
    _load_logging_config,
    _parse_bool,
)
from db_up.models import DatabaseConfig, MonitorConfig, LoggingConfig


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_config_from_env_vars(self, monkeypatch) -> None:
        """Test loading configuration from environment variables."""
        monkeypatch.setenv('DB_NAME', 'testdb')
        monkeypatch.setenv('DB_PASSWORD', 'testpass')
        monkeypatch.setenv('DB_HOST', 'testhost')
        monkeypatch.setenv('DB_PORT', '5433')
        
        config = load_config()
        
        assert config.database.database == 'testdb'
        assert config.database.password == 'testpass'
        assert config.database.host == 'testhost'
        assert config.database.port == 5433
    
    def test_load_config_with_file(self, tmp_path, monkeypatch) -> None:
        """Test loading configuration from YAML file."""
        monkeypatch.setenv('DB_PASSWORD', 'secret')
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
database:
  name: filedb
  host: filehost
  port: 5434
monitor:
  check_interval: 30
logging:
  level: DEBUG
""")
        
        config = load_config(str(config_file))
        
        assert config.database.database == 'filedb'
        assert config.database.host == 'filehost'
        assert config.database.port == 5434
        assert config.monitor.check_interval == 30
        assert config.logging.level == 'DEBUG'
    
    def test_env_vars_override_file(self, tmp_path, monkeypatch) -> None:
        """Test that environment variables override file config."""
        monkeypatch.setenv('DB_NAME', 'envdb')
        monkeypatch.setenv('DB_PASSWORD', 'secret')
        monkeypatch.setenv('DB_HOST', 'envhost')
        
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
database:
  name: filedb
  host: filehost
""")
        
        config = load_config(str(config_file))
        
        # Env vars should win
        assert config.database.database == 'envdb'
        assert config.database.host == 'envhost'


class TestLoadYamlConfig:
    """Tests for _load_yaml_config function."""
    
    def test_load_valid_yaml(self, tmp_path) -> None:
        """Test loading valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
database:
  name: mydb
  host: localhost
""")
        
        config = _load_yaml_config(str(config_file))
        
        assert config['database']['name'] == 'mydb'
        assert config['database']['host'] == 'localhost'
    
    def test_load_nonexistent_file_raises_error(self) -> None:
        """Test that loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc:
            _load_yaml_config('/nonexistent/config.yaml')
        
        assert 'not found' in str(exc.value)
    
    def test_load_invalid_yaml_raises_error(self, tmp_path) -> None:
        """Test that invalid YAML raises ValueError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
invalid: yaml: content:
  - broken
    indentation
""")
        
        with pytest.raises(ValueError) as exc:
            _load_yaml_config(str(config_file))
        
        assert 'Invalid YAML' in str(exc.value)
    
    def test_empty_yaml_returns_empty_dict(self, tmp_path) -> None:
        """Test that empty YAML file returns empty dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        
        config = _load_yaml_config(str(config_file))
        
        assert config == {}


class TestLoadDatabaseConfig:
    """Tests for _load_database_config function."""
    
    def test_load_from_env_vars(self, monkeypatch) -> None:
        """Test loading database config from environment variables."""
        monkeypatch.setenv('DB_NAME', 'testdb')
        monkeypatch.setenv('DB_PASSWORD', 'testpass')
        monkeypatch.setenv('DB_HOST', 'testhost')
        monkeypatch.setenv('DB_PORT', '5433')
        monkeypatch.setenv('DB_USER', 'testuser')
        monkeypatch.setenv('DB_SSL_MODE', 'verify-full')
        
        config = _load_database_config({})
        
        assert config.database == 'testdb'
        assert config.password == 'testpass'
        assert config.host == 'testhost'
        assert config.port == 5433
        assert config.user == 'testuser'
        assert config.ssl_mode == 'verify-full'
    
    def test_load_from_file_config(self, monkeypatch) -> None:
        """Test loading database config from file."""
        monkeypatch.setenv('DB_PASSWORD', 'secret')
        
        file_config = {
            'name': 'filedb',
            'host': 'filehost',
            'port': 5434,
            'user': 'fileuser',
        }
        
        config = _load_database_config(file_config)
        
        assert config.database == 'filedb'
        assert config.host == 'filehost'
        assert config.port == 5434
        assert config.user == 'fileuser'
    
    def test_defaults_applied(self, monkeypatch) -> None:
        """Test that defaults are applied when not specified."""
        monkeypatch.setenv('DB_NAME', 'testdb')
        monkeypatch.setenv('DB_PASSWORD', 'secret')
        
        config = _load_database_config({})
        
        assert config.host == 'localhost'
        assert config.port == 5432
        assert config.user == 'postgres'
        assert config.ssl_mode == 'require'
        assert config.ssl_verify is True
    
    def test_ssl_verify_false(self, monkeypatch) -> None:
        """Test that SSL_VERIFY=false disables certificate verification."""
        monkeypatch.setenv('DB_NAME', 'testdb')
        monkeypatch.setenv('DB_PASSWORD', 'secret')
        monkeypatch.setenv('SSL_VERIFY', 'false')
        
        config = _load_database_config({})
        
        assert config.ssl_verify is False
    
    def test_ssl_verify_true(self, monkeypatch) -> None:
        """Test that SSL_VERIFY=true enables certificate verification."""
        monkeypatch.setenv('DB_NAME', 'testdb')
        monkeypatch.setenv('DB_PASSWORD', 'secret')
        monkeypatch.setenv('SSL_VERIFY', 'true')
        
        config = _load_database_config({})
        
        assert config.ssl_verify is True


class TestParseDatabaseUrl:
    """Tests for _parse_database_url function."""
    
    def test_parse_full_url(self) -> None:
        """Test parsing complete DATABASE_URL."""
        url = "postgresql://myuser:mypass@myhost:5433/mydb"
        
        config = _parse_database_url(url)
        
        assert config.database == 'mydb'
        assert config.password == 'mypass'
        assert config.host == 'myhost'
        assert config.port == 5433
        assert config.user == 'myuser'
    
    def test_parse_url_with_postgres_scheme(self) -> None:
        """Test parsing URL with 'postgres://' scheme."""
        url = "postgres://user:pass@host/db"
        
        config = _parse_database_url(url)
        
        assert config.database == 'db'
        assert config.user == 'user'
    
    def test_parse_url_without_port(self) -> None:
        """Test parsing URL without port uses default."""
        url = "postgresql://user:pass@host/db"
        
        config = _parse_database_url(url)
        
        assert config.port == 5432
    
    def test_invalid_scheme_raises_error(self) -> None:
        """Test that invalid scheme raises ValueError."""
        url = "mysql://user:pass@host/db"
        
        with pytest.raises(ValueError) as exc:
            _parse_database_url(url)
        
        assert 'Invalid DATABASE_URL scheme' in str(exc.value)


class TestLoadMonitorConfig:
    """Tests for _load_monitor_config function."""
    
    def test_load_from_env_vars(self, monkeypatch) -> None:
        """Test loading monitor config from environment variables."""
        monkeypatch.setenv('DB_CHECK_INTERVAL', '30')
        monkeypatch.setenv('DB_MAX_RETRIES', '5')
        monkeypatch.setenv('DB_RETRY_BACKOFF', 'linear')
        monkeypatch.setenv('DB_RETRY_DELAY', '10')
        monkeypatch.setenv('DB_RETRY_JITTER', 'false')
        
        config = _load_monitor_config({})
        
        assert config.check_interval == 30
        assert config.max_retries == 5
        assert config.retry_backoff == 'linear'
        assert config.retry_delay == 10
        assert config.retry_jitter is False
    
    def test_load_from_file_config(self) -> None:
        """Test loading monitor config from file."""
        file_config = {
            'check_interval': 45,
            'max_retries': 2,
            'retry_backoff': 'fixed',
        }
        
        config = _load_monitor_config(file_config)
        
        assert config.check_interval == 45
        assert config.max_retries == 2
        assert config.retry_backoff == 'fixed'
    
    def test_defaults_applied(self) -> None:
        """Test that defaults are applied."""
        config = _load_monitor_config({})
        
        assert config.check_interval == 60
        assert config.max_retries == 3
        assert config.retry_backoff == 'exponential'
        assert config.retry_jitter is True


class TestLoadLoggingConfig:
    """Tests for _load_logging_config function."""
    
    def test_load_from_env_vars(self, monkeypatch) -> None:
        """Test loading logging config from environment variables."""
        monkeypatch.setenv('DB_LOG_LEVEL', 'DEBUG')
        monkeypatch.setenv('DB_LOG_OUTPUT', 'both')
        monkeypatch.setenv('DB_LOG_FILE', '/var/log/db-up.log')
        monkeypatch.setenv('DB_LOG_FORMAT', 'json')
        monkeypatch.setenv('DB_LOG_REDACT_CREDENTIALS', 'true')
        monkeypatch.setenv('DB_LOG_REDACT_HOSTNAMES', 'true')
        
        config = _load_logging_config({})
        
        assert config.level == 'DEBUG'
        assert config.output == 'both'
        assert config.file_path == '/var/log/db-up.log'
        assert config.format == 'json'
        assert config.redact_credentials is True
        assert config.redact_hostnames is True
    
    def test_load_from_file_config(self) -> None:
        """Test loading logging config from file."""
        file_config = {
            'level': 'WARNING',
            'output': 'file',
            'format': 'json',
        }
        
        config = _load_logging_config(file_config)
        
        assert config.level == 'WARNING'
        assert config.output == 'file'
        assert config.format == 'json'
    
    def test_defaults_applied(self) -> None:
        """Test that defaults are applied."""
        config = _load_logging_config({})
        
        assert config.level == 'INFO'
        assert config.output == 'console'
        assert config.format == 'text'
        assert config.redact_credentials is True
        assert config.redact_hostnames is False


class TestParseBool:
    """Tests for _parse_bool function."""
    
    def test_parse_true_values(self) -> None:
        """Test parsing various true values."""
        assert _parse_bool('true', False) is True
        assert _parse_bool('True', False) is True
        assert _parse_bool('TRUE', False) is True
        assert _parse_bool('1', False) is True
        assert _parse_bool('yes', False) is True
        assert _parse_bool('on', False) is True
    
    def test_parse_false_values(self) -> None:
        """Test parsing various false values."""
        assert _parse_bool('false', True) is False
        assert _parse_bool('False', True) is False
        assert _parse_bool('0', True) is False
        assert _parse_bool('no', True) is False
        assert _parse_bool('off', True) is False
    
    def test_parse_none_returns_default(self) -> None:
        """Test that None returns default value."""
        assert _parse_bool(None, True) is True
        assert _parse_bool(None, False) is False
    
    def test_parse_invalid_returns_false(self) -> None:
        """Test that invalid values return False."""
        assert _parse_bool('invalid', True) is False
        assert _parse_bool('maybe', True) is False


class TestIntegration:
    """Integration tests for configuration loading."""
    
    def test_complete_config_from_env(self, monkeypatch) -> None:
        """Test loading complete config from environment variables."""
        monkeypatch.setenv('DB_NAME', 'proddb')
        monkeypatch.setenv('DB_PASSWORD', 'prodsecret')
        monkeypatch.setenv('DB_HOST', 'prod.example.com')
        monkeypatch.setenv('DB_CHECK_INTERVAL', '120')
        monkeypatch.setenv('DB_LOG_LEVEL', 'WARNING')
        
        config = load_config()
        
        assert config.database.database == 'proddb'
        assert config.database.host == 'prod.example.com'
        assert config.monitor.check_interval == 120
        assert config.logging.level == 'WARNING'
    
    def test_database_url_takes_precedence(self, monkeypatch) -> None:
        """Test that DATABASE_URL takes precedence over individual vars."""
        monkeypatch.setenv('DATABASE_URL', 'postgresql://urluser:urlpass@urlhost:5433/urldb')
        monkeypatch.setenv('DB_NAME', 'ignored')
        monkeypatch.setenv('DB_HOST', 'ignored')
        
        config = load_config()
        
        assert config.database.database == 'urldb'
        assert config.database.host == 'urlhost'
        assert config.database.user == 'urluser'
        assert config.database.port == 5433

