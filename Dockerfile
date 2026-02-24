# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Zororo Phumulani â€” Dockerfile (Railway-hardened)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ENTIRE repo into /app
COPY . .

# Guarantee these dirs exist at runtime
RUN mkdir -p /app/static /app/templates /app/uploads

# Print structure at build time so Railway logs show it
RUN echo "=== BUILD: /app contents ===" && ls -la /app && \
    echo "=== static/ ===" && ls -la /app/static/ && \
    echo "=== templates/ ===" && ls -la /app/templates/

ENV PORT=8000

EXPOSE 8000

# Run from /app so __file__ and relative paths both resolve correctly
CMD ["sh", "-c", "cd /app && uvicorn main:app --host 0.0.0.0 --port $PORT"]

