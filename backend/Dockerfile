FROM python:3.11-slim

WORKDIR /app

# Install native dependencies required for vector libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Preload embedding models into cache (optional but recommended for faster startup)
ENV HF_HUB_DISABLE_SYMLINKS_WARNING=1
ENV TRANSFORMERS_VERBOSITY=error

COPY . .

# Setup volumes for persistent sqlite storage
RUN mkdir -p /app/data

EXPOSE 8000

# Run FastAPI behind Gunicorn for production concurrency
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
