FROM python:3.12-slim

WORKDIR /app

# Installa openssl per generare certificati self-signed (se non montati via volume)
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crea un utente non-root (Requisito Sezione 6: Security)
RUN useradd -m -r appuser && \
    openssl req -x509 -newkey rsa:4096 -nodes -out /app/cert.pem -keyout /app/key.pem -days 365 -subj "/CN=monster_service" && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5002

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--certfile", "/app/cert.pem", "--keyfile", "/app/key.pem", "app:app"]