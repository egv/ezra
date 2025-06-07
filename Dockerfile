FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY uv.lock ./

RUN uv sync --frozen

COPY . .

RUN mkdir -p /app/data && chmod 777 /app/data

ENV DATABASE_PATH=/app/data/ezra.db

VOLUME ["/app/data"]

EXPOSE 8080

USER root

CMD ["uv", "run", "python", "main.py"]