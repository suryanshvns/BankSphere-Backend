#!/usr/bin/env bash
# NEW admin / ops APIs only (for frontend integration).
# Set: BASE_URL (default below), ADMIN_TOKEN (Bearer JWT for an ADMIN).

set -o pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"
API="${BASE_URL}/api/v1"
AUTH=(-H "Authorization: Bearer ${ADMIN_TOKEN}")

# --- General ledger (double-entry from money movements) ---
curl -s "${API}/admin/ops/ledger/accounts" "${AUTH[@]}"
curl -s "${API}/admin/ops/ledger/journal-entries?take=50" "${AUTH[@]}"

# --- Outbound payment instructions (created by customer under /platform/payments/outbound) ---
curl -s -X POST "${API}/admin/ops/payment-instructions/PI_UUID/settle" "${AUTH[@]}"
curl -s -X POST "${API}/admin/ops/payment-instructions/PI_UUID/return" "${AUTH[@]}"

# --- Account holds (reduce customer available balance until released) ---
curl -s -X POST "${API}/admin/ops/accounts/ACCOUNT_UUID/holds" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"amount":"100.00","reason":"Compliance hold"}'
curl -s -X DELETE "${API}/admin/ops/holds/HOLD_UUID" "${AUTH[@]}"

# --- Maker–checker (e.g. MANUAL_CREDIT: payload account_id + amount) ---
curl -s -X POST "${API}/admin/ops/pending-actions" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"action_type":"MANUAL_CREDIT","payload":{"account_id":"ACCOUNT_UUID","amount":"50.00"}}'
curl -s "${API}/admin/ops/pending-actions" "${AUTH[@]}"
curl -s -X POST "${API}/admin/ops/pending-actions/PENDING_UUID/approve" "${AUTH[@]}" -H "Content-Type: application/json" -d '{"note":"OK"}'
curl -s -X POST "${API}/admin/ops/pending-actions/PENDING_UUID/reject" "${AUTH[@]}" -H "Content-Type: application/json" -d '{"note":"No"}'

# --- Screening stub (rules: name contains "pep" → REVIEW; email contains "sanction"/"blocked" → BLOCKED) ---
curl -s -X POST "${API}/admin/ops/users/USER_UUID/screening" "${AUTH[@]}"

# --- Data export queue (customer requests; you process to fill result_json) ---
curl -s "${API}/admin/ops/data-exports" "${AUTH[@]}"
curl -s -X POST "${API}/admin/ops/data-exports/EXPORT_UUID/process" "${AUTH[@]}"

# --- Webhook outbox (enqueue + list + simulated retry success) ---
curl -s -X POST "${API}/admin/ops/webhooks/enqueue" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"webhook_endpoint_id":"WEBHOOK_ENDPOINT_UUID","event_type":"loan.approved","body":{"loan_id":"x"}}'
curl -s "${API}/admin/ops/webhook-deliveries" "${AUTH[@]}"
curl -s -X POST "${API}/admin/ops/webhook-deliveries/DELIVERY_UUID/retry" "${AUTH[@]}"
