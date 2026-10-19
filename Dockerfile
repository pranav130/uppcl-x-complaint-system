FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and config
COPY uppcl_x_automation/ ./uppcl_x_automation/
COPY config/ ./config/
RUN mkdir -p data logs

ENV PYTHONUNBUFFERED=1
ENV DRY_RUN=false
ENV AUTO_POST_ENABLED=false
ENV PORT=10000

# Expose Render/Cloud web port
EXPOSE 10000

# Entrypoint runs server.py which starts both the HTTP health endpoint and background sync worker
CMD ["python", "-m", "uppcl_x_automation.server"]
