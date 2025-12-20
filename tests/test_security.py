"""
Tests for security module.

SECURITY: These tests are critical and must have 100% coverage.
"""

import pytest
from db_up.security import (
    sanitize_error,
    redact_connection_string,
    redact_config_for_logging,
    validate_webhook_url,
    validate_sql_query,
)


class TestSanitizeError:
    """Tests for sanitize_error function."""

    def test_password_equals_format(self) -> None:
        """SECURITY: Test password=value format is redacted."""
        error = "connection failed: password=secret123"
        sanitized = sanitize_error(error)

        assert "secret123" not in sanitized
        assert "password=***" in sanitized

    def test_password_colon_format(self) -> None:
        """SECURITY: Test password:value format is redacted."""
        error = "auth error: password:mysecret"
        sanitized = sanitize_error(error)

        assert "mysecret" not in sanitized
        assert "password=***" in sanitized

    def test_password_with_quotes(self) -> None:
        """SECURITY: Test password with quotes is redacted."""
        error = 'password="secret123"'
        sanitized = sanitize_error(error)

        assert "secret123" not in sanitized
        assert "password=***" in sanitized

    def test_connection_string_redaction(self) -> None:
        """SECURITY: Test full connection string is redacted."""
        error = "failed to connect: postgresql://user:secret@host:5432/db"
        sanitized = sanitize_error(error)

        assert "secret" not in sanitized
        assert "postgresql://***" in sanitized

    def test_db_password_env_var(self) -> None:
        """SECURITY: Test DB_PASSWORD environment variable is redacted."""
        error = "DB_PASSWORD=supersecret not set"
        sanitized = sanitize_error(error)

        assert "supersecret" not in sanitized
        assert "DB_PASSWORD=***" in sanitized

    def test_database_url_redaction(self) -> None:
        """SECURITY: Test DATABASE_URL is redacted."""
        error = "DATABASE_URL=postgresql://user:pass@host/db"
        sanitized = sanitize_error(error)

        assert "pass" not in sanitized
        assert "DATABASE_URL=***" in sanitized

    def test_ip_address_redaction_when_enabled(self) -> None:
        """SECURITY: Test IP addresses are redacted when enabled."""
        error = "connection to 192.168.1.100 failed"
        sanitized = sanitize_error(error, redact_hostnames=True)

        assert "192.168.1.100" not in sanitized
        assert "***" in sanitized

    def test_ip_address_not_redacted_by_default(self) -> None:
        """Test IP addresses are not redacted by default."""
        error = "connection to 192.168.1.100 failed"
        sanitized = sanitize_error(error, redact_hostnames=False)

        assert "192.168.1.100" in sanitized

    def test_localhost_redaction_when_enabled(self) -> None:
        """Test localhost is redacted when enabled."""
        error = "connecting to localhost:5432"
        sanitized = sanitize_error(error, redact_hostnames=True)

        assert "localhost" not in sanitized
        assert "***" in sanitized

    def test_empty_string(self) -> None:
        """Test empty string returns empty string."""
        assert sanitize_error("") == ""
        assert sanitize_error(None) is None

    def test_multiple_passwords(self) -> None:
        """SECURITY: Test multiple passwords are all redacted."""
        error = "password=secret1 and DB_PASSWORD=secret2"
        sanitized = sanitize_error(error)

        assert "secret1" not in sanitized
        assert "secret2" not in sanitized
        assert sanitized.count("***") >= 2

    def test_case_insensitive(self) -> None:
        """SECURITY: Test redaction is case-insensitive."""
        error = "PASSWORD=secret123"
        sanitized = sanitize_error(error)

        assert "secret123" not in sanitized
        assert "***" in sanitized


class TestRedactConnectionString:
    """Tests for redact_connection_string function."""

    def test_basic_connection_string(self) -> None:
        """Test basic connection string redaction."""
        conn_str = "postgresql://user:secret@host:5432/db"
        redacted = redact_connection_string(conn_str)

        assert "secret" not in redacted
        assert "postgresql://user:***@host:5432/db" == redacted

    def test_empty_string(self) -> None:
        """Test empty string returns empty string."""
        assert redact_connection_string("") == ""
        assert redact_connection_string(None) is None

    def test_no_password_in_string(self) -> None:
        """Test connection string without password."""
        conn_str = "postgresql://host:5432/db"
        redacted = redact_connection_string(conn_str)

        assert redacted == conn_str


class TestRedactConfigForLogging:
    """Tests for redact_config_for_logging function."""

    def test_redact_password_field(self) -> None:
        """SECURITY: Test password field is redacted."""
        config = {
            "host": "localhost",
            "password": "secret123",
            "port": 5432,
        }

        redacted = redact_config_for_logging(config)

        assert redacted["password"] == "***"
        assert redacted["host"] == "localhost"
        assert redacted["port"] == 5432

    def test_original_not_modified(self) -> None:
        """Test original config is not modified."""
        config = {"password": "secret"}
        redacted = redact_config_for_logging(config)

        assert config["password"] == "secret"  # Original unchanged
        assert redacted["password"] == "***"  # Copy redacted

    def test_nested_config(self) -> None:
        """SECURITY: Test nested password fields are redacted."""
        config = {
            "database": {
                "host": "localhost",
                "password": "secret",
            },
            "api_key": "key123",
        }

        redacted = redact_config_for_logging(config)

        assert redacted["database"]["password"] == "***"
        assert redacted["api_key"] == "***"
        assert redacted["database"]["host"] == "localhost"

    def test_various_sensitive_field_names(self) -> None:
        """SECURITY: Test various sensitive field names are redacted."""
        config = {
            "password": "pass1",
            "passwd": "pass2",
            "pwd": "pass3",
            "secret": "secret1",
            "token": "token1",
            "api_key": "key1",
            "apikey": "key2",
            "connection_uri": "uri1",
            "database_url": "url1",
        }

        redacted = redact_config_for_logging(config)

        for key in config.keys():
            assert redacted[key] == "***", f"Field {key} should be redacted"

    def test_case_insensitive_field_names(self) -> None:
        """SECURITY: Test field name matching is case-insensitive."""
        config = {
            "PASSWORD": "secret",
            "Password": "secret2",
        }

        redacted = redact_config_for_logging(config)

        assert redacted["PASSWORD"] == "***"
        assert redacted["Password"] == "***"

    def test_list_in_config(self) -> None:
        """Test config with lists is handled correctly."""
        config = {
            "databases": [
                {"host": "host1", "password": "pass1"},
                {"host": "host2", "password": "pass2"},
            ]
        }

        redacted = redact_config_for_logging(config)

        assert redacted["databases"][0]["password"] == "***"
        assert redacted["databases"][1]["password"] == "***"
        assert redacted["databases"][0]["host"] == "host1"


class TestValidateWebhookUrl:
    """Tests for validate_webhook_url function."""

    def test_none_url_is_valid(self) -> None:
        """Test None URL is valid (webhooks disabled)."""
        assert validate_webhook_url(None) is True
        assert validate_webhook_url("") is True

    def test_https_url_is_valid(self) -> None:
        """Test HTTPS URL is valid."""
        assert validate_webhook_url("https://example.com/webhook") is True

    def test_http_url_raises_error(self) -> None:
        """SECURITY: Test HTTP URL is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("http://example.com/webhook")

        assert "must use HTTPS" in str(exc.value)

    def test_localhost_raises_error(self) -> None:
        """SECURITY: Test localhost is rejected (SSRF prevention)."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("https://localhost/webhook")

        assert "localhost" in str(exc.value).lower()
        assert "SSRF" in str(exc.value)

    def test_loopback_ip_raises_error(self) -> None:
        """SECURITY: Test loopback IP is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("https://127.0.0.1/webhook")

        assert "internal IP" in str(exc.value)
        assert "SSRF" in str(exc.value)

    def test_private_class_a_raises_error(self) -> None:
        """SECURITY: Test private class A IP is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("https://10.0.0.1/webhook")

        assert "internal IP" in str(exc.value)

    def test_private_class_b_raises_error(self) -> None:
        """SECURITY: Test private class B IP is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("https://172.16.0.1/webhook")

        assert "internal IP" in str(exc.value)

    def test_private_class_c_raises_error(self) -> None:
        """SECURITY: Test private class C IP is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("https://192.168.1.1/webhook")

        assert "internal IP" in str(exc.value)

    def test_link_local_raises_error(self) -> None:
        """SECURITY: Test link-local IP is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("https://169.254.169.254/webhook")

        assert "internal IP" in str(exc.value)

    def test_invalid_url_raises_error(self) -> None:
        """Test invalid URL raises error."""
        with pytest.raises(ValueError) as exc:
            validate_webhook_url("not-a-url")

        assert "HTTPS" in str(exc.value)


class TestValidateSqlQuery:
    """Tests for validate_sql_query function."""

    def test_simple_select_is_valid(self) -> None:
        """Test simple SELECT query is valid."""
        assert validate_sql_query("SELECT 1") is True
        assert validate_sql_query("SELECT 1 AS health_check") is True
        assert validate_sql_query("SELECT version()") is True

    def test_select_with_trailing_semicolon_is_valid(self) -> None:
        """Test SELECT with trailing semicolon is valid."""
        assert validate_sql_query("SELECT 1;") is True

    def test_empty_query_raises_error(self) -> None:
        """Test empty query raises error."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("")

        assert "cannot be empty" in str(exc.value)

    def test_non_select_raises_error(self) -> None:
        """SECURITY: Test non-SELECT query raises error."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("UPDATE users SET active=1")

        assert "must be a SELECT statement" in str(exc.value)

    def test_drop_table_raises_error(self) -> None:
        """SECURITY: Test DROP TABLE is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("SELECT 1; DROP TABLE users")

        assert "DROP" in str(exc.value)

    def test_delete_raises_error(self) -> None:
        """SECURITY: Test DELETE is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("SELECT 1; DELETE FROM users")

        assert "DELETE" in str(exc.value)

    def test_insert_raises_error(self) -> None:
        """SECURITY: Test INSERT is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("SELECT 1; INSERT INTO users VALUES (1)")

        assert "INSERT" in str(exc.value)

    def test_update_raises_error(self) -> None:
        """SECURITY: Test UPDATE is rejected."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("SELECT 1; UPDATE users SET x=1")

        assert "UPDATE" in str(exc.value)

    def test_multiple_statements_raises_error(self) -> None:
        """SECURITY: Test multiple statements are rejected."""
        with pytest.raises(ValueError) as exc:
            validate_sql_query("SELECT 1; SELECT 2")

        assert "multiple statements" in str(exc.value)

    def test_case_insensitive(self) -> None:
        """Test validation is case-insensitive."""
        assert validate_sql_query("select 1") is True
        assert validate_sql_query("SeLeCt 1") is True

        with pytest.raises(ValueError):
            validate_sql_query("select 1; drop table users")
