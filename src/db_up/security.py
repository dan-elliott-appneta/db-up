"""
Security functions for db-up.

This module provides security-critical functionality including:
- Credential redaction from logs and error messages
- Sensitive data sanitization
- Input validation

SECURITY: All functions in this module must be thoroughly tested.
"""

import re
from typing import Any, Dict, Optional


def sanitize_error(error: str, redact_hostnames: bool = False) -> str:
    """
    Sanitize error messages to remove sensitive information.

    This function removes:
    - Passwords (in various formats)
    - Connection strings
    - Optionally: IP addresses and hostnames

    Args:
        error: The error message to sanitize
        redact_hostnames: If True, also redact IP addresses

    Returns:
        Sanitized error message with sensitive data replaced

    Examples:
        >>> sanitize_error("password=secret123")
        'password=***'
        >>> sanitize_error("postgresql://user:pass@host/db")
        'postgresql://***'
    """
    if not error:
        return error

    sanitized = error

    # Remove passwords in various formats
    # password=value, password:value, password='value', password="value"
    sanitized = re.sub(
        r'password["\']?\s*[:=]\s*["\']?([^\s"\']+)',
        "password=***",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Remove passwords from connection strings
    # postgresql://user:password@host/db -> postgresql://***
    sanitized = re.sub(
        r"postgresql://[^:]+:([^@]+)@",
        "postgresql://***@",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Remove full connection URIs
    sanitized = re.sub(
        r"postgresql://[^\s]+", "postgresql://***", sanitized, flags=re.IGNORECASE
    )

    # Remove DB_PASSWORD environment variable values
    sanitized = re.sub(
        r'DB_PASSWORD["\']?\s*[:=]\s*["\']?([^\s"\']+)',
        "DB_PASSWORD=***",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Remove DATABASE_URL values
    sanitized = re.sub(
        r'DATABASE_URL["\']?\s*[:=]\s*["\']?([^\s"\']+)',
        "DATABASE_URL=***",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Optionally redact IP addresses
    if redact_hostnames:
        # IPv4 addresses
        sanitized = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "***", sanitized)
        # Common internal hostnames
        sanitized = re.sub(
            r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b",
            "***",
            sanitized,
            flags=re.IGNORECASE,
        )

    return sanitized


def redact_connection_string(conn_string: str) -> str:
    """
    Redact sensitive information from a connection string.

    Args:
        conn_string: Database connection string

    Returns:
        Redacted connection string safe for logging

    Examples:
        >>> redact_connection_string("postgresql://user:secret@host:5432/db")
        'postgresql://user:***@host:5432/db'
    """
    if not conn_string:
        return conn_string

    # Redact password in connection string
    redacted = re.sub(
        r"(postgresql://[^:]+:)([^@]+)(@)", r"\1***\3", conn_string, flags=re.IGNORECASE
    )

    return redacted


def redact_config_for_logging(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive fields from a configuration dictionary for logging.

    This creates a copy of the config with sensitive fields replaced.

    Args:
        config_dict: Configuration dictionary

    Returns:
        New dictionary with sensitive fields redacted

    Examples:
        >>> config = {"password": "secret", "host": "localhost"}
        >>> redact_config_for_logging(config)
        {'password': '***', 'host': 'localhost'}
    """
    import copy

    # Create a deep copy to avoid modifying the original
    redacted = copy.deepcopy(config_dict)

    # List of sensitive field names (case-insensitive)
    sensitive_fields = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "connection_uri",
        "database_url",
    ]

    def redact_recursive(obj: Any) -> None:
        """Recursively redact sensitive fields."""
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if key.lower() in sensitive_fields:
                    obj[key] = "***"
                elif isinstance(obj[key], (dict, list)):
                    redact_recursive(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    redact_recursive(item)

    redact_recursive(redacted)
    return redacted


def validate_webhook_url(url: Optional[str]) -> bool:
    """
    Validate webhook URL to prevent SSRF attacks.

    SECURITY: This function prevents webhooks to internal IP addresses
    and requires HTTPS for security.

    Args:
        url: Webhook URL to validate

    Returns:
        True if URL is safe, False otherwise

    Raises:
        ValueError: If URL is unsafe with explanation
    """
    if not url:
        return True  # None/empty is acceptable (webhooks disabled)

    # Must use HTTPS
    if not url.startswith("https://"):
        raise ValueError(
            "Webhook URL must use HTTPS for security. " f"Got: {url[:20]}..."
        )

    # Extract hostname from URL
    # https://example.com/webhook -> example.com
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError(f"Invalid webhook URL: {url[:50]}...")

    # Block internal/private IP addresses
    internal_patterns = [
        r"^127\.",  # Loopback
        r"^10\.",  # Private class A
        r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",  # Private class B
        r"^192\.168\.",  # Private class C
        r"^169\.254\.",  # Link-local
        r"^0\.0\.0\.0$",  # Unspecified
        r"^255\.255\.255\.255$",  # Broadcast
    ]

    for pattern in internal_patterns:
        if re.match(pattern, hostname):
            raise ValueError(
                f"Webhook URL cannot point to internal IP address: {hostname}. "
                "This could be a security risk (SSRF attack)."
            )

    # Block localhost
    if hostname.lower() in ["localhost", "localhost.localdomain"]:
        raise ValueError(
            "Webhook URL cannot point to localhost. "
            "This could be a security risk (SSRF attack)."
        )

    return True


def validate_sql_query(query: str) -> bool:
    """
    Validate SQL query to prevent injection attacks.

    SECURITY: Only allows simple SELECT queries for health checks.

    Args:
        query: SQL query to validate

    Returns:
        True if query is safe

    Raises:
        ValueError: If query contains dangerous statements
    """
    if not query:
        raise ValueError("Query cannot be empty")

    query_upper = query.strip().upper()

    # Must start with SELECT
    if not query_upper.startswith("SELECT"):
        raise ValueError(
            "Health check query must be a SELECT statement. " f"Got: {query[:50]}..."
        )

    # Block dangerous keywords
    dangerous_keywords = [
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
    ]

    for keyword in dangerous_keywords:
        if keyword in query_upper:
            raise ValueError(
                f"Health check query cannot contain '{keyword}' statement. "
                "Only simple SELECT queries are allowed for security."
            )

    # Block semicolons (multiple statements)
    if ";" in query and not query.strip().endswith(";"):
        raise ValueError(
            "Health check query cannot contain multiple statements. "
            "Only a single SELECT query is allowed."
        )

    return True
