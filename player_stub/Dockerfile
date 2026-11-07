FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY player_stub.py .

RUN useradd --uid 10004 --no-create-home stub
USER stub

EXPOSE 5001
# Same port and HTTPS as the real Player Service; it reads the token key from /certs.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "1", "--threads", "4", \
     "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", \
     "player_stub:create_stub()"]
