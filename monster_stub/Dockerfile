FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY stub.py .

RUN useradd --uid 10003 --no-create-home stub
USER stub

EXPOSE 5002
# Same port and HTTPS as the real Monster Service. One process, so /__calls sees every call.
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "1", "--threads", "4", \
     "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", \
     "stub:app"]
