FROM python:3.12-slim

WORKDIR /app

# Install openssl to generate a self-signed certificate for HTTPS (Requisite Section 6: Security)
# Verify that the public key is available either via the JWT_PUBLIC_KEY environment variable or via a mounted file at
# o JWT_PUBLIC_KEY_PATH (/certs/jwt_public.pem).
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create a non-root user to run the application and generate a self-signed certificate for HTTPS.
RUN useradd -m -r appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5002

CMD ["gunicorn", "-b", "0.0.0.0:5002", "app:create_app()"]