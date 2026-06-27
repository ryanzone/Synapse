FROM python:3.12-slim

LABEL maintainer="Synapse" \
    description="Synapse autonomous AI platform — backend service"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose the FastAPI port
EXPOSE 8000

# Non-root user for security
RUN useradd -m -u 1000 synapse \
    && chown -R synapse:synapse /app
USER synapse

ENTRYPOINT ["/app/entrypoint.sh"]