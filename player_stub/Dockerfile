FROM python:3.12-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /player_stub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -r stub && \
    chown -R stub:stub /player_stub

USER stub

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5010", "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", "app:app"]