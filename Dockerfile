# Dockerfile for Simplex KG-RAG System
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY .env .

# Create necessary directories
RUN mkdir -p data/raw data/processed data/csv_export

# Expose API port
EXPOSE 8000

# Set Python path
ENV PYTHONPATH=/app

# Run the API by default
CMD ["python", "scripts/run_api.py"]