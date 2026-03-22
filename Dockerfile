FROM python:3.12-slim

WORKDIR /app

# Prisma engines need a working SSL stack; libstdc++ avoids some engine load failures on slim images.
# Node + npm must exist on PATH as `node` / `npm` so prisma-client-py does not use nodeenv (often fails on Render).
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl ca-certificates libstdc++6 \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && if ! command -v node >/dev/null 2>&1 && command -v nodejs >/dev/null 2>&1; then \
         ln -sf "$(command -v nodejs)" /usr/local/bin/node; \
       fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prisma ./prisma
COPY app ./app
COPY scripts ./scripts

ENV PYTHONPATH=/app
ENV PRISMA_GENERATE_DATAPROXY=false

# Generate once at image build (requires global Node above; avoids nodeenv + generate on every boot).
RUN python -m prisma generate

EXPOSE 8000

# Migrations: run locally via scripts/sync_neon_db.sh (or add prisma migrate deploy here).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
