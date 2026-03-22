FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prisma ./prisma
COPY app ./app
COPY scripts ./scripts

ENV PYTHONPATH=/app
ENV PRISMA_GENERATE_DATAPROXY=false

RUN prisma generate

EXPOSE 8000

# Render sets PORT at runtime; default 8000 for local Docker.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
