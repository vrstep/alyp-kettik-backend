FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for bcrypt, asyncpg, and OpenCV (headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libpq-dev libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
