FROM python:3.12-slim

WORKDIR /gateway

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -r appuser && \
    chown -R appuser:appuser /gateway

USER appuser

EXPOSE 5005

CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", "app:app"]