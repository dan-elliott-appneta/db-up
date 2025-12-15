"""
Main application entry point for db-up.

This module provides the main application loop and CLI interface.
"""

import sys
import signal
import time
import argparse
from typing import Optional

from db_up.config import load_config
from db_up.logger import setup_logging, get_logger
from db_up.db_checker import DatabaseChecker
from db_up.models import Config


class Application:
    """
    Main application class for db-up.
    
    This class manages the application lifecycle:
    - Configuration loading
    - Logging setup
    - Database health checking
    - Graceful shutdown
    """
    
    def __init__(self, config: Config):
        """
        Initialize the application.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.running = False
        self.logger = setup_logging(config.logging)
        self.checker = DatabaseChecker(
            config.database,
            redact_hostnames=config.logging.redact_hostnames
        )
        self.check_count = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: any) -> None:
        """
        Handle shutdown signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received {signal_name}, shutting down gracefully...")
        self.running = False
    
    def run_once(self) -> int:
        """
        Run a single health check.
        
        This is useful for testing or one-off checks.
        
        Returns:
            Exit code: 0 for success, 1 for failure
        """
        self.logger.info("Running single health check...")
        
        result = self.checker.check_connection()
        
        if result.is_success():
            self.logger.info(
                f"✓ Health check passed - Response time: {result.response_time_ms:.0f}ms"
            )
            return 0
        else:
            self.logger.error(
                f"✗ Health check failed - {result.error_code}: {result.error_message}"
            )
            return 1
    
    def run(self) -> None:
        """
        Run the main application loop.
        
        This continuously monitors the database at the configured interval
        until interrupted.
        """
        self.running = True
        self.logger.info(
            f"Starting db-up monitor - "
            f"Database: {self.config.database.database}@{self.config.database.host}:{self.config.database.port}, "
            f"Check interval: {self.config.monitor.check_interval}s"
        )
        
        while self.running:
            self.check_count += 1
            
            try:
                result = self.checker.check_connection()
                
                if result.is_success():
                    self.logger.info(
                        f"Health check passed - Response time: {result.response_time_ms:.0f}ms",
                        extra={
                            'response_time_ms': result.response_time_ms,
                            'status': 'success',
                            'check_number': self.check_count,
                        }
                    )
                else:
                    self.logger.warning(
                        f"Health check failed - {result.error_code}: {result.error_message}",
                        extra={
                            'response_time_ms': result.response_time_ms,
                            'status': 'failure',
                            'error_code': result.error_code,
                            'error_message': result.error_message,
                            'check_number': self.check_count,
                        }
                    )
            
            except Exception as e:
                self.logger.error(
                    f"Unexpected error during health check: {e}",
                    exc_info=True
                )
            
            # Wait for next check (if still running)
            if self.running:
                time.sleep(self.config.monitor.check_interval)
        
        self.logger.info(
            f"Shutting down after {self.check_count} health checks"
        )


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='db-up: PostgreSQL database connectivity monitor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variables (recommended)
  export DB_NAME=mydb DB_PASSWORD=secret
  db-up
  
  # Using config file
  db-up --config config.yaml
  
  # One-time check
  db-up --once
  
  # Custom interval
  db-up --interval 30

For more information, visit: https://github.com/yourusername/db-up
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to configuration file (YAML)'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run health check once and exit'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='db-up 1.0.0'
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the application.
    
    Returns:
        Exit code: 0 for success, 1 for failure
    """
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Load configuration
        try:
            config = load_config(args.config)
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            return 1
        
        # Create and run application
        app = Application(config)
        
        if args.once:
            return app.run_once()
        else:
            app.run()
            return 0
    
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT
    
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

