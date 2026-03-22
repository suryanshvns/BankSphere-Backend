#!/usr/bin/env bash
# NEW customer-facing APIs only (for frontend integration).
# Set: BASE_URL (default below), ACCESS_TOKEN (Bearer JWT for a USER).

set -o pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"
API="${BASE_URL}/api/v1"
AUTH=(-H "Authorization: Bearer ${ACCESS_TOKEN}")

# --- MFA (TOTP) ---
curl -s -X POST "${API}/platform/mfa/enroll/start" "${AUTH[@]}"
# → data.secret, data.otpauth_url — confirm with TOTP from authenticator app:
curl -s -X POST "${API}/platform/mfa/enroll/confirm" "${AUTH[@]}" -H "Content-Type: application/json" -d '{"code":"123456"}'
curl -s -X POST "${API}/platform/mfa/disable" "${AUTH[@]}" -H "Content-Type: application/json" -d '{"password":"YOUR_PASSWORD"}'

# --- Outbound payment instructions (ACH_SIM | WIRE_SIM | RTP_SIM) ---
curl -s -X POST "${API}/platform/payments/outbound" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"from_account_id":"ACCOUNT_UUID","amount":"25.00","rail":"ACH_SIM","idempotency_key":"pi-unique-001","counterparty":{"name":"Merchant","account_last4":"1234"},"reference":"INV-001"}'
curl -s "${API}/platform/payments/outbound" "${AUTH[@]}"

# --- Card: authorize → capture (or reverse before capture) ---
curl -s -X POST "${API}/platform/cards/CARD_UUID/authorize" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"amount":"10.00","merchant_name":"Store","idempotency_key":"card-auth-001"}'
curl -s -X POST "${API}/platform/cards/CARD_UUID/capture" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"authorization_id":"AUTH_UUID","from_account_id":"ACCOUNT_UUID","idempotency_key":"card-cap-001"}'
curl -s -X POST "${API}/platform/cards/authorizations/AUTH_UUID/reverse" "${AUTH[@]}"

# --- Loan installments (rows created when admin approves the loan) ---
curl -s "${API}/loans/LOAN_UUID/installments" "${AUTH[@]}"
curl -s -X POST "${API}/loans/LOAN_UUID/installments/1/pay" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"from_account_id":"ACCOUNT_UUID"}'

# --- Support cases ---
curl -s -X POST "${API}/platform/support/cases" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"subject":"Need help","body":"Details…","priority":1}'
curl -s "${API}/platform/support/cases" "${AUTH[@]}"

# --- KYB (business profile) ---
curl -s -X POST "${API}/platform/business/profile" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"company_name":"Acme LLC","registration_number":"REG-123","country":"US"}'

# --- Privacy / DSAR-style export (admin processes → customer downloads JSON) ---
curl -s -X POST "${API}/platform/privacy/data-export" "${AUTH[@]}"
curl -s "${API}/platform/privacy/data-export/EXPORT_UUID" "${AUTH[@]}"
