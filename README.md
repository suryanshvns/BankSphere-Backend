# BankSphere — Core Banking Backend

Production-style **FastAPI** API with **PostgreSQL** and **Prisma ORM** (Prisma Client Python), layered as **API → services → repositories**, JWT auth, atomic money movements, idempotent writes, audit logging, and basic rate limiting.

## Prerequisites

- Python **3.10+** (Docker image uses 3.12)
- PostgreSQL **16** (or use Docker Compose)
- Prisma CLI (installed with `pip install prisma`)

## Quick start (local)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# .env is included for local testing; edit DATABASE_URL / SECRET_KEY if needed
prisma generate
docker compose up -d db     # or use your own Postgres
prisma migrate deploy
python scripts/seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)  
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Seed users (after `scripts/seed.py`)

| Email | Password | Role |
|-------|----------|------|
| `admin@example.com` | `Admin123!@#` | ADMIN |
| `alice@example.com` | `User123456!` | USER |

For **heavy demo data** (customer + admin UIs: ~180 users, transactions, loans, KYC/loan queues), run `python scripts/seed_full_demo.py` and see **`docs/SEED_DEMO.md`** for all logins.

## Docker (API + Postgres)

```bash
docker compose up --build
```

The API service runs `prisma migrate deploy`, then `scripts/seed.py`, then Uvicorn. Postgres is exposed on host port **5433** by default.

## Database migrations (Prisma)

```bash
# After editing prisma/schema.prisma (dev)
prisma migrate dev --name describe_change

# Apply existing migrations (CI / production)
prisma migrate deploy
```

Migrations live in `prisma/migrations/`.

## API prefix

All routes are under **`/api/v1/`** except OpenAPI static paths (`/docs`, `/openapi.json`).

---

## cURL reference (every endpoint)

Replace `TOKEN` and IDs with values from your environment. Base URL: `http://localhost:8000`.

### 1. Health

```bash
curl -s http://localhost:8000/api/v1/health
```

### 2. Signup

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@example.com","password":"LongPass123","full_name":"Bob"}'
```

### 3. Login

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"User123456!"}'
```

### 4. Current user (`Authorization` required)

```bash
curl -s http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer TOKEN"
```

### 5. Submit KYC reference (audit + notification; status stays until admin updates)

```bash
curl -s -X POST http://localhost:8000/api/v1/users/me/kyc/submit \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reference_id":"DOC-2026-0001"}'
```

### 6. Create account

```bash
curl -s -X POST http://localhost:8000/api/v1/accounts \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"SAVINGS","currency":"USD"}'
```

### 7. List my accounts

```bash
curl -s http://localhost:8000/api/v1/accounts \
  -H "Authorization: Bearer TOKEN"
```

### 8. Get account by ID

```bash
curl -s http://localhost:8000/api/v1/accounts/ACCOUNT_UUID \
  -H "Authorization: Bearer TOKEN"
```

### 9. Deposit (idempotency key required)

```bash
curl -s -X POST http://localhost:8000/api/v1/transactions/deposit \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"ACCOUNT_UUID","amount":"250.00","idempotency_key":"idem-deposit-0001","description":"ATM deposit"}'
```

### 10. Withdraw

```bash
curl -s -X POST http://localhost:8000/api/v1/transactions/withdraw \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"ACCOUNT_UUID","amount":"25.00","idempotency_key":"idem-withdraw-0001","description":"ATM cash"}'
```

### 11. Transfer between accounts

```bash
curl -s -X POST http://localhost:8000/api/v1/transactions/transfer \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_account_id":"FROM_UUID","to_account_id":"TO_UUID","amount":"10.00","idempotency_key":"idem-transfer-0001","description":"Rent"}'
```

### 12. List my transactions (via owned accounts)

```bash
curl -s http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer TOKEN"
```

### 13. Get transaction by ID

```bash
curl -s http://localhost:8000/api/v1/transactions/TRANSACTION_UUID \
  -H "Authorization: Bearer TOKEN"
```

### 14. Apply for a loan (EMI computed server-side)

```bash
curl -s -X POST http://localhost:8000/api/v1/loans/apply \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"principal":"50000.00","annual_rate_pct":"10.5","tenure_months":36,"purpose":"Home improvement"}'
```

### 15. List my loans

```bash
curl -s http://localhost:8000/api/v1/loans \
  -H "Authorization: Bearer TOKEN"
```

### 16. Get loan by ID

```bash
curl -s http://localhost:8000/api/v1/loans/LOAN_UUID \
  -H "Authorization: Bearer TOKEN"
```

### 17. Notifications (mock — stored as `AuditLog` rows with `action=NOTIFICATION`)

```bash
curl -s http://localhost:8000/api/v1/notifications \
  -H "Authorization: Bearer TOKEN"
```

### 18. Admin — set user KYC status

```bash
curl -s -X PATCH http://localhost:8000/api/v1/admin/users/USER_UUID/kyc \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kyc_status":"VERIFIED"}'
```

`kyc_status` enum: `PENDING`, `VERIFIED`, `REJECTED`.

### 19. Admin — approve or reject loan

```bash
curl -s -X PATCH http://localhost:8000/api/v1/admin/loans/LOAN_UUID/status \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"APPROVED"}'
```

Use `"REJECTED"` to reject. Only `APPROVED` and `REJECTED` are accepted from admin.

---

## Security notes

- Set a strong **`SECRET_KEY`** in production (env).
- JWT is validated on protected routes via **`HTTPBearer`** and **`Depends(get_current_user)`** (FastAPI-native pattern).
- Passwords hashed with **bcrypt**; roles **`USER`** / **`ADMIN`**; users carry **KYC** status.
- **Rate limiting:** default **200 requests/minute** per IP (`slowapi`).

## Project layout

```
backend/
  app/
    api/v1/          # Routers (thin)
    core/            # Config, security, deps, rate limit, exceptions
    models/          # Placeholder; Prisma generates real models
    repositories/    # Prisma data access
    schemas/         # Pydantic request/response DTOs
    services/        # Business logic + transactions
    utils/
    main.py
  prisma/
    schema.prisma
    migrations/
  scripts/
    seed.py
```

## License

Educational / demonstration codebase.
# BankSphere-Backend
