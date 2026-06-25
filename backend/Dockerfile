FROM python:3.11-slim

WORKDIR /app

# Ensure logs are not buffered so they show up immediately in the console
ENV PYTHONUNBUFFERED=1

# Install native dependencies required for vector libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Preload embedding models into cache
ENV HF_HUB_DISABLE_SYMLINKS_WARNING=1
ENV TRANSFORMERS_VERBOSITY=error

# Create a non-root user with UID 1000 (Required for Hugging Face Spaces)
RUN useradd -m -u 1000 user

COPY . .

# Setup volumes for persistent sqlite storage and give ownership to the new user
RUN mkdir -p /app/data && chown -R user:user /app

# Switch to the non-root user
USER user

# Expose port 7860 (Default for Hugging Face)
EXPOSE 7860

# Run FastAPI behind Gunicorn, binding to 7860
CMD ["gunicorn", "app.main:app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:7860"]