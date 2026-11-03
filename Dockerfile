FROM python:3.12-slim

WORKDIR /project

# Copy dependency metadata first so this step can be cached independently
# from changes to the application source code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code changes now invalidate only this later copy step.
COPY . .

EXPOSE 5005

CMD ["flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5005"]