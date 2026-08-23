FROM python:3.14-slim
LABEL org.opencontainers.image.title="meta-mcp-server"
LABEL org.opencontainers.image.description="Meta Marketing MCP Server — 199 tools for Facebook/Instagram/WhatsApp"
LABEL org.opencontainers.image.source="https://github.com/ahmedalbanna/meta-mcp-server"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (layer cache)
COPY requirements.txt pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e . --no-deps

# Copy source code (never copy .env — secrets must be injected at runtime via env vars or mounted file)
COPY server.py webhook_server.py ./
COPY scripts/ ./scripts/
COPY reports/.gitkeep ./reports/.gitkeep
COPY media/.gitkeep ./media/.gitkeep

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from src.config import validate_config; import sys; sys.exit(0 if not validate_config() else 1)" || exit 1

# Run the server with streamable-http transport for Docker connectivity
ENV MCP_TRANSPORT=streamable-http
EXPOSE 8000 8080
CMD ["python", "/app/server.py"]