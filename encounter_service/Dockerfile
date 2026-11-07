FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Requirements §6: the container runs as a normal user, never as root.
RUN useradd --uid 10002 --no-create-home encounter
USER encounter

ENV PYTHONUNBUFFERED=1
EXPOSE 5003
# HTTPS with the certificate that tls-init put in this service's volume (/certs).
# One worker keeps the first start (tables and the 16 challenges) free of races.
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "--workers", "1", "--threads", "4", \
     "--certfile", "/certs/server.pem", "--keyfile", "/certs/server.key", \
     "--access-logfile", "-", \
     "app:create_app()"]
