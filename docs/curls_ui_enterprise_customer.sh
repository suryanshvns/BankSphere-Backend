#!/usr/bin/env bash
# Enterprise / full-platform customer APIs (double-entry is automatic on money movement).
# Prereq: migrate + seed; export ACCESS_TOKEN (customer JWT).

set -o pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API="${BASE_URL}/api/v1"
H="Authorization: Bearer ${ACCESS_TOKEN:-}"

# --- MFA (TOTP) ---
# POST /platform/mfa/enroll/start → data.secret, data.otpauth_url
[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s -X POST "${API}/platform/mfa/enroll/start" -H "$H" | python3 -m json.tool && echo

# POST /platform/mfa/enroll/confirm  body: { "code": "123456" }
[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s -X POST "${API}/platform/mfa/enroll/confirm" -H "$H" -H "Content-Type: application/json" \
  -d '{"code":"<TOTP>"}' | python3 -m json.tool && echo

# POST /platform/mfa/disable  body: { "password": "..." }
[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s -X POST "${API}/platform/mfa/disable" -H "$H" -H "Content-Type: application/json" \
  -d '{"password":"<PASSWORD>"}' | python3 -m json.tool && echo

# --- Outbound payment rails (ACH_SIM / WIRE_SIM / RTP_SIM) ---
[[ -n "${ACCESS_TOKEN:-}" && -n "${ACCOUNT_ID:-}" ]] && curl -s -X POST "${API}/platform/payments/outbound" -H "$H" -H "Content-Type: application/json" \
  -d "{\"from_account_id\":\"${ACCOUNT_ID}\",\"amount\":\"25.00\",\"rail\":\"ACH_SIM\",\"idempotency_key\":\"ach-$(date +%s)\",\"counterparty\":{\"name\":\"ACME Corp\",\"account_last4\":\"9876\"}}" | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s "${API}/platform/payments/outbound" -H "$H" | python3 -m json.tool && echo

# --- Card auth / capture ---
[[ -n "${ACCESS_TOKEN:-}" && -n "${CARD_ID:-}" ]] && curl -s -X POST "${API}/platform/cards/${CARD_ID}/authorize" -H "$H" -H "Content-Type: application/json" \
  -d "{\"amount\":\"15.00\",\"merchant_name\":\"Coffee Shop\",\"idempotency_key\":\"auth-$(date +%s)\"}" | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" && -n "${CARD_ID:-}" && -n "${AUTH_ID:-}" && -n "${ACCOUNT_ID:-}" ]] && curl -s -X POST "${API}/platform/cards/${CARD_ID}/capture" -H "$H" -H "Content-Type: application/json" \
  -d "{\"authorization_id\":\"${AUTH_ID}\",\"from_account_id\":\"${ACCOUNT_ID}\",\"idempotency_key\":\"cap-$(date +%s)\"}" | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" && -n "${AUTH_ID:-}" ]] && curl -s -X POST "${API}/platform/cards/authorizations/${AUTH_ID}/reverse" -H "$H" | python3 -m json.tool && echo

# --- Loan installments (persisted when admin approves loan) ---
[[ -n "${ACCESS_TOKEN:-}" && -n "${LOAN_ID:-}" ]] && curl -s "${API}/loans/${LOAN_ID}/installments" -H "$H" | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" && -n "${LOAN_ID:-}" && -n "${ACCOUNT_ID:-}" ]] && curl -s -X POST "${API}/loans/${LOAN_ID}/installments/1/pay" -H "$H" -H "Content-Type: application/json" \
  -d "{\"from_account_id\":\"${ACCOUNT_ID}\"}" | python3 -m json.tool && echo

# --- Support + KYB + privacy export ---
[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s -X POST "${API}/platform/support/cases" -H "$H" -H "Content-Type: application/json" \
  -d '{"subject":"Cannot link account","body":"Details...","priority":1}' | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s "${API}/platform/support/cases" -H "$H" | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s -X POST "${API}/platform/business/profile" -H "$H" -H "Content-Type: application/json" \
  -d '{"company_name":"Acme LLC","registration_number":"EIN-12-3456789","country":"US"}' | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" ]] && curl -s -X POST "${API}/platform/privacy/data-export" -H "$H" | python3 -m json.tool && echo

[[ -n "${ACCESS_TOKEN:-}" && -n "${EXPORT_ID:-}" ]] && curl -s "${API}/platform/privacy/data-export/${EXPORT_ID}" -H "$H" | python3 -m json.tool && echo

# --- Account balance now includes available_balance & hold_balance ---
[[ -n "${ACCESS_TOKEN:-}" && -n "${ACCOUNT_ID:-}" ]] && curl -s "${API}/accounts/${ACCOUNT_ID}/balance" -H "$H" | python3 -m json.tool && echo
