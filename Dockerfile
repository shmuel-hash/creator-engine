## Stage 1: Build the Vite frontend
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend-vite/package.json frontend-vite/package-lock.json* ./
RUN npm install
COPY frontend-vite/ .
RUN npm run build

## Stage 2: Python app
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy the Vite build output into the frontend directory
COPY --from=frontend-build /build/dist /app/frontend/dist

# Remove .env if it got copied (Railway uses its own env vars)
RUN rm -f .env

# Railway sets PORT dynamically
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
