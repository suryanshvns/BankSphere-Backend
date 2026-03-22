#!/usr/bin/env bash
# Enterprise admin / ops APIs (maker-checker, holds, ledger, rails settlement, compliance stubs).
# export ADMIN_TOKEN=...

set -o pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API="${BASE_URL}/api/v1"
AH="Authorization: Bearer ${ADMIN_TOKEN:-}"

# --- General ledger (double-entry journal from customer money movements) ---
[[ -n "${ADMIN_TOKEN:-}" ]] && curl -s "${API}/admin/ops/ledger/accounts" -H "$AH" | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" ]] && curl -s "${API}/admin/ops/ledger/journal-entries?take=20" -H "$AH" | python3 -m json.tool && echo

# --- Settle / return outbound payment instructions ---
[[ -n "${ADMIN_TOKEN:-}" && -n "${PI_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/payment-instructions/${PI_ID}/settle" -H "$AH" | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" && -n "${PI_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/payment-instructions/${PI_ID}/return" -H "$AH" | python3 -m json.tool && echo

# --- Account holds (reduce available balance) ---
[[ -n "${ADMIN_TOKEN:-}" && -n "${ACCOUNT_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/accounts/${ACCOUNT_ID}/holds" -H "$AH" -H "Content-Type: application/json" \
  -d '{"amount":"100.00","reason":"Fraud review"}' | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" && -n "${HOLD_ID:-}" ]] && curl -s -X DELETE "${API}/admin/ops/holds/${HOLD_ID}" -H "$AH" | python3 -m json.tool && echo

# --- Maker–checker manual credit ---
[[ -n "${ADMIN_TOKEN:-}" && -n "${TARGET_ACCOUNT_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/pending-actions" -H "$AH" -H "Content-Type: application/json" \
  -d "{\"action_type\":\"MANUAL_CREDIT\",\"payload\":{\"account_id\":\"${TARGET_ACCOUNT_ID}\",\"amount\":\"50.00\"}}" | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" ]] && curl -s "${API}/admin/ops/pending-actions" -H "$AH" | python3 -m json.tool && echo

# Approve / reject (checker must be a different admin user than maker)
[[ -n "${ADMIN_TOKEN:-}" && -n "${PENDING_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/pending-actions/${PENDING_ID}/approve" -H "$AH" -H "Content-Type: application/json" \
  -d '{"note":"Approved"}' | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" && -n "${PENDING_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/pending-actions/${PENDING_ID}/reject" -H "$AH" -H "Content-Type: application/json" \
  -d '{"note":"Rejected"}' | python3 -m json.tool && echo

# --- AML/KYC screening stub (email contains "sanction" or "blocked" → BLOCKED; name contains "pep" → REVIEW) ---
[[ -n "${ADMIN_TOKEN:-}" && -n "${USER_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/users/${USER_ID}/screening" -H "$AH" | python3 -m json.tool && echo

# --- DSAR-style export (customer requests; admin builds JSON snapshot) ---
[[ -n "${ADMIN_TOKEN:-}" ]] && curl -s "${API}/admin/ops/data-exports" -H "$AH" | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" && -n "${EXPORT_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/data-exports/${EXPORT_ID}/process" -H "$AH" | python3 -m json.tool && echo

# --- Webhook outbox (enqueue + retry; retry simulates success) ---
[[ -n "${ADMIN_TOKEN:-}" && -n "${WEBHOOK_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/webhooks/enqueue" -H "$AH" -H "Content-Type: application/json" \
  -d "{\"webhook_endpoint_id\":\"${WEBHOOK_ID}\",\"event_type\":\"loan.approved\",\"body\":{\"loan_id\":\"x\"}}" | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" ]] && curl -s "${API}/admin/ops/webhook-deliveries" -H "$AH" | python3 -m json.tool && echo

[[ -n "${ADMIN_TOKEN:-}" && -n "${DELIVERY_ID:-}" ]] && curl -s -X POST "${API}/admin/ops/webhook-deliveries/${DELIVERY_ID}/retry" -H "$AH" | python3 -m json.tool && echo
