FROM python:3.12-slim

WORKDIR /gateway

RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /certs && \
    openssl req -x509 -newkey rsa:4096 -nodes -out /certs/server.pem -keyout /certs/server.key -days 365 -subj "/CN=gateway" && \
    useradd -m -r appuser && \
    chown -R appuser:appuser /certs /gateway

USER appuser

EXPOSE 5005

CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", "app:app"]