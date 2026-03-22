FROM python:3.12-slim

WORKDIR /app

# Prisma engines need a working SSL stack; libstdc++ avoids some engine load failures on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prisma ./prisma
COPY app ./app
COPY scripts ./scripts

ENV PYTHONPATH=/app
ENV PRISMA_GENERATE_DATAPROXY=false

# Do NOT run `prisma generate` here — it often fails on Render’s build hosts (engine/arch/network).
# Generate runs at container start on the same Linux arch as runtime (see CMD below).

EXPOSE 8000

# Generate client, then start API. Migrations: run locally via scripts/sync_neon_db.sh (or add prisma migrate deploy here).
CMD ["sh", "-c", "python -m prisma generate && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
