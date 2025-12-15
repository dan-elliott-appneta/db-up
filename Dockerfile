# Multi-stage build for minimal final image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash dbup

# Set working directory
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /root/.local /home/dbup/.local

# Copy application code
COPY src/ ./src/
COPY setup.py pyproject.toml ./

# Install application
RUN pip install --no-cache-dir -e .

# Create logs directory
RUN mkdir -p /app/logs && chown -R dbup:dbup /app

# Switch to non-root user
USER dbup

# Set PATH to include user-installed packages
ENV PATH=/home/dbup/.local/bin:$PATH

# Default command
ENTRYPOINT ["db-up"]
CMD []

