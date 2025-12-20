"""
db-up: A simple tool to monitor PostgreSQL database connectivity.

This package provides a lightweight monitoring solution for PostgreSQL databases,
checking connectivity at configurable intervals with comprehensive logging and
security features.
"""

__version__ = "1.0.0"
__all__ = [
    "HealthCheckResult",
    "DatabaseChecker",
    "Application",
    "load_config",
    "setup_logging",
]

from db_up.models import HealthCheckResult
from db_up.db_checker import DatabaseChecker
from db_up.main import Application
from db_up.config import load_config
from db_up.logger import setup_logging
