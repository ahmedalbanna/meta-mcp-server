FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (never copy .env — secrets must be injected at runtime via env vars or mounted file)
COPY src/ /app/src/
COPY server.py /app/
COPY webhook_server.py /app/
COPY pyproject.toml /app/
COPY requirements.txt /app/requirements.txt

# Run the server with streamable-http transport for Docker connectivity
CMD ["python", "/app/server.py"]