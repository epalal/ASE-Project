FROM python:3.12-slim

WORKDIR /player_service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -r appuser && \
    chown -R appuser:appuser /player_service

USER appuser

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", "app:app"]