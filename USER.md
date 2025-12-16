# db-up User Manual

**Version 1.0.0**

A comprehensive guide to using db-up, the PostgreSQL database connectivity monitoring tool.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Logging](#logging)
7. [Deployment](#deployment)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [FAQ](#faq)

---

## Introduction

### What is db-up?

db-up is a simple, secure tool that continuously monitors PostgreSQL database connectivity. It performs health checks at configurable intervals and provides detailed logging of connection status.

### Key Features

- 🔒 **Secure by Default**: SSL/TLS required, passwords only from environment variables
- 📊 **Configurable Logging**: Multiple log levels, formats, and outputs
- 🔄 **Smart Retries**: Automatic retry with exponential backoff
- 🐳 **Docker Ready**: Easy containerized deployment
- 🧪 **Production Tested**: 171 tests with 97% coverage

### When to Use db-up

Use db-up when you need to:
- Monitor database availability continuously
- Get alerted when database connections fail
- Track database response times
- Verify database accessibility in production
- Monitor database connectivity in Kubernetes/Docker environments

---

## Installation

### Prerequisites

- Python 3.8 or higher
- PostgreSQL database (any version)
- pip (Python package installer)

### Method 1: Install from Source

```bash
# Clone or download the repository
cd db-up

# Install the package
pip install -e .

# Verify installation
db-up --version
```

### Method 2: Docker

```bash
# Pull the image (when published)
docker pull db-up:latest

# Or build locally
docker build -t db-up:latest .
```

### Verify Installation

```bash
db-up --help
```

You should see the help message with available options.

---

## Quick Start

### 1. Set Required Environment Variables

The only required variables are the database name and password:

```bash
export DB_NAME=mydb
export DB_PASSWORD=your_password
```

### 2. Run the Monitor

```bash
db-up
```

That's it! The tool will start monitoring your database every 60 seconds.

### 3. Stop the Monitor

Press `Ctrl+C` to stop gracefully. The tool will finish the current check and shut down cleanly.

---

## Configuration

### Configuration Methods

db-up supports three configuration methods with the following priority:

1. **Command Line Arguments** (highest priority)
2. **Environment Variables**
3. **Configuration File**
4. **Default Values** (lowest priority)

### Environment Variables

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_NAME` | Database name | `mydb` |
| `DB_PASSWORD` | Database password | `secret123` |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | Database hostname or IP | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_USER` | Database username | `postgres` |
| `DB_SSL_MODE` | SSL mode | `require` |
| `SSL_VERIFY` | Verify SSL certificates (true/false) | `true` |
| `DATABASE_URL` | Full connection URI | - |
| `DB_CHECK_INTERVAL` | Seconds between checks | `60` |
| `DB_MAX_RETRIES` | Maximum retry attempts | `3` |
| `DB_LOG_LEVEL` | Log level | `INFO` |
| `DB_LOG_FORMAT` | Log format | `text` |
| `DB_LOG_OUTPUT` | Output destination | `console` |

#### Using DATABASE_URL

For Heroku or cloud deployments:

```bash
export DATABASE_URL=postgresql://user:password@host:5432/dbname
db-up
```

### Configuration File

Create a `config.yaml` file:

```yaml
database:
  host: localhost
  port: 5432
  name: mydb
  user: postgres
  ssl_mode: require

monitor:
  check_interval: 60
  max_retries: 3
  retry_backoff: exponential
  retry_delay: 5
  retry_jitter: true

logging:
  level: INFO
  output: console
  format: text
```

**Important**: Never put passwords in the config file! Always use environment variables.

Run with config file:

```bash
export DB_PASSWORD=secret
db-up --config config.yaml
```

### SSL Configuration

db-up requires SSL by default for security. Available SSL modes:

| Mode | Description | Security Level |
|------|-------------|----------------|
| `disable` | No SSL (not recommended) | ⚠️ Low |
| `allow` | Try SSL, fallback to no SSL | ⚠️ Low |
| `prefer` | Prefer SSL, fallback to no SSL | ⚠️ Medium |
| `require` | Require SSL (default) | ✅ High |
| `verify-ca` | Require SSL, verify CA | ✅ Very High |
| `verify-full` | Require SSL, verify CA and hostname | ✅ Maximum |

**Recommendation**: Use `require` or higher in production.

```bash
export DB_SSL_MODE=require
```

#### Disabling SSL Certificate Verification

**⚠️ Warning**: Only use this in development/testing environments with self-signed certificates.

If you need to connect to a database with a self-signed certificate or skip certificate verification:

```bash
export SSL_VERIFY=false
export DB_SSL_MODE=require
db-up
```

When `SSL_VERIFY=false`:
- SSL connection is still required
- Certificate verification is skipped
- ⚠️ This reduces security and should NOT be used in production
- Useful for development environments with self-signed certificates

**Production**: Always keep `SSL_VERIFY=true` (default) for security.

---

## Usage

### Basic Usage

#### Continuous Monitoring

Monitor database continuously (default behavior):

```bash
export DB_NAME=mydb DB_PASSWORD=secret
db-up
```

Output:
```
2025-12-15 10:30:45 [INFO] Starting db-up monitor - Database: mydb@localhost:5432, Check interval: 60s
2025-12-15 10:30:45 [INFO] Health check passed - Response time: 45ms
2025-12-15 10:31:45 [INFO] Health check passed - Response time: 42ms
```

#### One-Time Check

Run a single health check and exit:

```bash
db-up --once
```

Exit codes:
- `0`: Success (database is accessible)
- `1`: Failure (database is not accessible)

This is useful for:
- Testing connectivity
- Health check scripts
- CI/CD pipelines

### Command Line Options

```bash
db-up [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--config FILE` | `-c` | Path to configuration file |
| `--once` | - | Run single check and exit |
| `--version` | `-v` | Show version and exit |
| `--help` | `-h` | Show help message |

### Examples

#### Example 1: Development Environment

```bash
# Local PostgreSQL with debug logging
export DB_NAME=devdb
export DB_PASSWORD=devpass
export DB_LOG_LEVEL=DEBUG
db-up
```

#### Example 2: Production Environment

```bash
# Production with JSON logging to file
export DB_NAME=proddb
export DB_PASSWORD=$PROD_PASSWORD
export DB_HOST=prod.example.com
export DB_SSL_MODE=verify-full
export DB_LOG_LEVEL=INFO
export DB_LOG_FORMAT=json
export DB_LOG_OUTPUT=both
db-up --config /etc/db-up/config.yaml
```

#### Example 3: Quick Test

```bash
# Test if database is accessible
export DB_NAME=mydb DB_PASSWORD=secret
if db-up --once; then
    echo "Database is up!"
else
    echo "Database is down!"
fi
```

#### Example 4: Custom Interval

```bash
# Check every 30 seconds
export DB_NAME=mydb
export DB_PASSWORD=secret
export DB_CHECK_INTERVAL=30
db-up
```

---

## Logging

### Log Levels

#### DEBUG
Most verbose, shows all details:
- Connection parameters (passwords redacted)
- SSL negotiation details
- Retry calculations
- Configuration loaded

Use for: Troubleshooting connection issues

```bash
export DB_LOG_LEVEL=DEBUG
```

#### INFO (Default)
Normal operation information:
- Successful health checks with response time
- Application startup and shutdown
- Connection state changes

Use for: Production monitoring

```bash
export DB_LOG_LEVEL=INFO
```

#### WARNING
Important but non-critical issues:
- Failed health checks (with retries)
- Configuration warnings
- Resource warnings

Use for: Production with reduced logging

```bash
export DB_LOG_LEVEL=WARNING
```

#### ERROR
Errors requiring attention:
- Authentication failures
- Persistent connection failures
- Configuration errors

Use for: Production with minimal logging

```bash
export DB_LOG_LEVEL=ERROR
```

### Log Formats

#### Text Format (Human-Readable)

Default for console output:

```
2025-12-15 10:30:45 [INFO] Health check passed - Response time: 45ms
2025-12-15 10:31:45 [WARNING] Health check failed - CONNECTION_ERROR: Connection refused
```

#### JSON Format (Machine-Readable)

Recommended for production and log aggregation:

```json
{
  "timestamp": "2025-12-15T10:30:45.123Z",
  "level": "INFO",
  "message": "Health check passed",
  "response_time_ms": 45,
  "status": "success",
  "application": "db-up"
}
```

Enable JSON format:

```bash
export DB_LOG_FORMAT=json
```

### Log Outputs

#### Console Only (Default)

```bash
export DB_LOG_OUTPUT=console
db-up
```

#### File Only

```bash
export DB_LOG_OUTPUT=file
export DB_LOG_FILE=/var/log/db-up/monitor.log
db-up
```

#### Both Console and File

```bash
export DB_LOG_OUTPUT=both
db-up
```

### Log Rotation

Logs automatically rotate when they reach the maximum size:

```bash
export DB_LOG_MAX_SIZE=10485760  # 10MB
export DB_LOG_BACKUP_COUNT=5     # Keep 5 old logs
```

Files created:
- `db-up.log` (current)
- `db-up.log.1` (most recent backup)
- `db-up.log.2`
- ...
- `db-up.log.5` (oldest backup)

### Security: Automatic Redaction

**All passwords and credentials are automatically removed from logs:**

```
# What you log:
"Connection failed: password=secret123"

# What appears in logs:
"Connection failed: password=***"
```

This happens automatically - you don't need to do anything!

---

## Deployment

### Standalone Script

#### Systemd Service (Linux)

Create `/etc/systemd/system/db-up.service`:

```ini
[Unit]
Description=Database Connectivity Monitor
After=network.target

[Service]
Type=simple
User=dbmonitor
EnvironmentFile=/etc/db-up/environment
ExecStart=/usr/local/bin/db-up --config /etc/db-up/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Create `/etc/db-up/environment`:

```bash
DB_NAME=mydb
DB_PASSWORD=secret
DB_HOST=localhost
```

Enable and start:

```bash
sudo systemctl enable db-up
sudo systemctl start db-up
sudo systemctl status db-up
```

### Docker

#### Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db-monitor:
    image: db-up:latest
    environment:
      DB_HOST: postgres
      DB_NAME: mydb
      DB_USER: postgres
      DB_PASSWORD: secret
      DB_CHECK_INTERVAL: 60
      DB_LOG_LEVEL: INFO
    restart: unless-stopped
```

Run:

```bash
docker-compose up -d
docker-compose logs -f db-monitor
```

#### Using Docker Run

```bash
docker run -d \
  --name db-monitor \
  -e DB_HOST=postgres \
  -e DB_NAME=mydb \
  -e DB_PASSWORD=secret \
  -e DB_CHECK_INTERVAL=60 \
  --restart unless-stopped \
  db-up:latest
```

### Kubernetes

Create `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: db-monitor
spec:
  replicas: 1
  selector:
    matchLabels:
      app: db-monitor
  template:
    metadata:
      labels:
        app: db-monitor
    spec:
      containers:
      - name: db-monitor
        image: db-up:latest
        env:
        - name: DB_HOST
          value: postgres-service
        - name: DB_NAME
          value: mydb
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: password
        - name: DB_CHECK_INTERVAL
          value: "60"
        - name: DB_LOG_FORMAT
          value: json
```

Create secret:

```bash
kubectl create secret generic db-credentials \
  --from-literal=username=postgres \
  --from-literal=password=secret
```

Deploy:

```bash
kubectl apply -f deployment.yaml
kubectl logs -f deployment/db-monitor
```

---

## Troubleshooting

### Common Issues

#### Issue: "Database password is required"

**Cause**: DB_PASSWORD environment variable not set

**Solution**:
```bash
export DB_PASSWORD=your_password
db-up
```

#### Issue: "Authentication failed"

**Cause**: Incorrect username or password

**Solutions**:
1. Verify credentials:
   ```bash
   psql -h localhost -U postgres -d mydb
   ```

2. Check environment variables:
   ```bash
   echo $DB_USER
   echo $DB_PASSWORD
   ```

3. Try with correct credentials:
   ```bash
   export DB_USER=postgres
   export DB_PASSWORD=correct_password
   db-up --once
   ```

#### Issue: "Connection refused"

**Cause**: PostgreSQL not running or not accessible

**Solutions**:
1. Check if PostgreSQL is running:
   ```bash
   # Linux
   systemctl status postgresql
   
   # macOS
   brew services list
   
   # Docker
   docker ps | grep postgres
   ```

2. Check if port is open:
   ```bash
   telnet localhost 5432
   # or
   nc -zv localhost 5432
   ```

3. Check firewall rules:
   ```bash
   sudo ufw status  # Ubuntu
   sudo firewall-cmd --list-all  # CentOS/RHEL
   ```

4. Verify host and port:
   ```bash
   export DB_HOST=localhost
   export DB_PORT=5432
   db-up --once
   ```

#### Issue: "SSL connection required"

**Cause**: Server requires SSL but ssl_mode is set to disable

**Solution**:
```bash
export DB_SSL_MODE=require
db-up
```

For development only (not recommended):
```bash
export DB_SSL_MODE=disable
db-up
```

#### Issue: "Database 'mydb' does not exist"

**Cause**: Database name is incorrect or database doesn't exist

**Solutions**:
1. List available databases:
   ```bash
   psql -h localhost -U postgres -l
   ```

2. Create the database:
   ```bash
   createdb mydb
   ```

3. Use correct database name:
   ```bash
   export DB_NAME=correct_name
   db-up --once
   ```

#### Issue: "Too many connections"

**Cause**: PostgreSQL max_connections limit reached

**Solutions**:
1. Check current connections:
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   ```

2. Increase max_connections in postgresql.conf:
   ```
   max_connections = 200
   ```

3. Restart PostgreSQL:
   ```bash
   sudo systemctl restart postgresql
   ```

### Debug Mode

Enable debug logging to see detailed information:

```bash
export DB_LOG_LEVEL=DEBUG
db-up
```

Debug output includes:
- Connection parameters (passwords redacted)
- SSL negotiation details
- Retry calculations
- Configuration values

### Getting Help

If you encounter issues:

1. Check the logs with DEBUG level
2. Verify your configuration
3. Test database connection manually with `psql`
4. Review the [Troubleshooting](#troubleshooting) section
5. Check GitHub issues

---

## Best Practices

### Security

#### 1. Never Store Passwords in Config Files

❌ **Bad**:
```yaml
database:
  password: secret123  # Never do this!
```

✅ **Good**:
```bash
export DB_PASSWORD=secret123
```

#### 2. Use SSL/TLS in Production

```bash
export DB_SSL_MODE=require  # or verify-full
```

#### 3. Use Dedicated Monitoring User

Create a user with minimal privileges:

```sql
CREATE USER db_monitor WITH PASSWORD 'your_password';
GRANT CONNECT ON DATABASE mydb TO db_monitor;
```

```bash
export DB_USER=db_monitor
export DB_PASSWORD=monitor_password
```

#### 4. Secure Configuration Files

```bash
chmod 600 config.yaml
chown dbmonitor:dbmonitor config.yaml
```

### Monitoring

#### 1. Use Appropriate Check Intervals

- **Production**: 60 seconds (default)
- **Development**: 30 seconds
- **Critical systems**: 10-15 seconds
- **Non-critical**: 120-300 seconds

```bash
export DB_CHECK_INTERVAL=60
```

#### 2. Enable JSON Logging in Production

```bash
export DB_LOG_FORMAT=json
export DB_LOG_OUTPUT=both
```

#### 3. Set Up Log Rotation

```bash
export DB_LOG_MAX_SIZE=10485760  # 10MB
export DB_LOG_BACKUP_COUNT=5
```

#### 4. Monitor the Monitor

Use systemd, Docker restart policies, or Kubernetes to ensure db-up stays running.

### Performance

#### 1. Don't Check Too Frequently

Checking every second creates unnecessary load:

```bash
# ❌ Too frequent
export DB_CHECK_INTERVAL=1

# ✅ Reasonable
export DB_CHECK_INTERVAL=60
```

#### 2. Use Connection Pooling

If running multiple monitors, use a connection pooler like PgBouncer.

#### 3. Set Appropriate Timeouts

```bash
export DB_CONNECT_TIMEOUT=5
export DB_STATEMENT_TIMEOUT=5
```

---

## FAQ

### General Questions

**Q: What databases does db-up support?**

A: Currently only PostgreSQL. Support for MySQL and other databases may be added in the future.

**Q: Can I monitor multiple databases?**

A: Currently, each instance of db-up monitors one database. Run multiple instances to monitor multiple databases.

**Q: Does db-up require any special database permissions?**

A: No, it only requires the `CONNECT` privilege. It doesn't read or write any data.

**Q: How much overhead does db-up add?**

A: Minimal. Each check opens one connection, runs `SELECT 1`, and closes the connection. Memory usage is ~20MB.

### Configuration Questions

**Q: Can I use a connection string instead of individual parameters?**

A: Yes, use the `DATABASE_URL` environment variable:
```bash
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**Q: How do I change the log level at runtime?**

A: Currently, you need to restart db-up with a new log level. Runtime changes may be added in the future.

**Q: Where are logs stored by default?**

A: By default, logs go to console. Use `DB_LOG_OUTPUT=file` to log to `logs/db-up.log`.

### Troubleshooting Questions

**Q: Why am I seeing "password=***" in error messages?**

A: This is a security feature. All passwords are automatically redacted from logs to prevent credential leakage.

**Q: The tool says "Health check passed" but my application can't connect. Why?**

A: db-up only checks basic connectivity. Your application might have different permissions, use a different database, or have other issues.

**Q: Can I disable SSL for testing?**

A: Yes, but not recommended:
```bash
export DB_SSL_MODE=disable
```

### Deployment Questions

**Q: Can I run db-up in Kubernetes?**

A: Yes! See the [Kubernetes](#kubernetes) section for deployment examples.

**Q: Should I run multiple instances for high availability?**

A: db-up is a monitoring tool, not a critical service. One instance is usually sufficient. If it fails, you'll notice when monitoring stops.

**Q: How do I integrate with Prometheus/Grafana?**

A: This feature is planned for a future release. Currently, parse JSON logs for metrics.

---

## Appendix

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failure (connection failed, configuration error) |
| 130 | Interrupted by user (Ctrl+C) |

### Environment Variable Reference

Complete list of all environment variables:

```bash
# Database Connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=postgres
DB_PASSWORD=secret
DB_SSL_MODE=require
SSL_VERIFY=true
DB_CONNECT_TIMEOUT=5
DB_STATEMENT_TIMEOUT=5
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Monitoring
DB_CHECK_INTERVAL=60
DB_MAX_RETRIES=3
DB_RETRY_BACKOFF=exponential
DB_RETRY_DELAY=5
DB_RETRY_JITTER=true
DB_READ_ONLY_MODE=true

# Logging
DB_LOG_LEVEL=INFO
DB_LOG_OUTPUT=console
DB_LOG_FORMAT=text
DB_LOG_FILE=logs/db-up.log
DB_LOG_MAX_SIZE=10485760
DB_LOG_BACKUP_COUNT=5
DB_LOG_REDACT_CREDENTIALS=true
DB_LOG_REDACT_HOSTNAMES=false
```

### Support and Resources

- **Documentation**: See README.md and PLAN.md
- **Issues**: Report bugs on GitHub
- **Source Code**: Available on GitHub
- **License**: MIT License

---

**Last Updated**: December 15, 2025  
**Version**: 1.0.0

