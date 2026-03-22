#!/usr/bin/env bash
# Run from your laptop against Neon (or any Postgres): regenerate Prisma client + apply migrations.
# Prereq: Python venv with `pip install -r requirements.txt` (includes prisma).
#
# Usage:
#   ./scripts/sync_neon_db.sh
#   ./scripts/sync_neon_db.sh status   # only prisma migrate status
#
# Loads variables from .env in the repo root. If DATABASE_URL contains &, the value must be
# in single quotes in .env, e.g. DATABASE_URL='postgresql://...?sslmode=require&channel_binding=require'

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set. Put it in .env (quote the URL if it contains &)." >&2
  exit 1
fi

if [[ -x "$ROOT/.venv/bin/prisma" ]]; then
  PRISMA="$ROOT/.venv/bin/prisma"
elif command -v prisma >/dev/null 2>&1; then
  PRISMA="prisma"
else
  echo "ERROR: prisma CLI not found. Run:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

echo "Using DATABASE_URL from environment (.env)."
echo "→ prisma generate"
"$PRISMA" generate

if [[ "${1:-}" == "status" ]]; then
  echo "→ prisma migrate status"
  "$PRISMA" migrate status
  exit 0
fi

echo "→ prisma migrate deploy"
"$PRISMA" migrate deploy

echo "Done. Neon is up to date with prisma/migrations."
