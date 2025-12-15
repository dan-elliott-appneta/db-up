"""
db-up: A simple tool to monitor PostgreSQL database connectivity.

This package provides a lightweight monitoring solution for PostgreSQL databases,
checking connectivity at configurable intervals with comprehensive logging and
security features.
"""

__version__ = "1.0.0"
__all__ = ["DatabaseMonitor", "HealthCheckResult"]

from db_up.models import HealthCheckResult
from db_up.monitor import DatabaseMonitor

