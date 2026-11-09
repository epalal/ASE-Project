FROM python:3.12-slim

WORKDIR /app

# Install dependencies for Python and database
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create a non-root user to run the application and generate a self-signed certificate for HTTPS.
RUN useradd -m -r appuser && \
    openssl req -x509 -newkey rsa:4096 -nodes -out /app/cert.pem -keyout /app/key.pem -days 365 -subj "/CN=player_service" && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--certfile", "/app/cert.pem", "--keyfile", "/app/key.pem", "app:app"]