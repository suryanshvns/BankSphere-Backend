-- Extend TransactionKind
ALTER TYPE "TransactionKind" ADD VALUE IF NOT EXISTS 'CARD_CAPTURE';

-- New enums
CREATE TYPE "LedgerAccountType" AS ENUM ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE');
CREATE TYPE "LedgerSide" AS ENUM ('DEBIT', 'CREDIT');
CREATE TYPE "PaymentRail" AS ENUM ('ACH_SIM', 'WIRE_SIM', 'RTP_SIM', 'INTERNAL');
CREATE TYPE "PaymentInstructionStatus" AS ENUM ('PENDING', 'SUBMITTED', 'SETTLED', 'RETURNED', 'FAILED');
CREATE TYPE "CardAuthorizationStatus" AS ENUM ('AUTHORIZED', 'CAPTURED', 'REVERSED');
CREATE TYPE "LoanInstallmentStatus" AS ENUM ('PENDING', 'PAID', 'OVERDUE');
CREATE TYPE "PendingAdminActionStatus" AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
CREATE TYPE "SupportCaseStatus" AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED');
CREATE TYPE "ScreeningResultStatus" AS ENUM ('CLEAR', 'REVIEW', 'BLOCKED');
CREATE TYPE "DataExportStatus" AS ENUM ('REQUESTED', 'READY', 'FAILED');
CREATE TYPE "KybStatus" AS ENUM ('PENDING', 'VERIFIED', 'REJECTED');

-- User MFA
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "mfa_totp_secret" TEXT;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "mfa_enabled" BOOLEAN NOT NULL DEFAULT false;

-- Account holds
ALTER TABLE "Account" ADD COLUMN IF NOT EXISTS "hold_balance" DECIMAL(18,2) NOT NULL DEFAULT 0;

-- Ledger
CREATE TABLE "LedgerAccount" (
    "id" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" "LedgerAccountType" NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "LedgerAccount_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "LedgerAccount_code_key" ON "LedgerAccount"("code");

CREATE TABLE "JournalEntry" (
    "id" TEXT NOT NULL,
    "transaction_id" TEXT,
    "memo" TEXT,
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "posted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "JournalEntry_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "JournalEntry_transaction_id_key" ON "JournalEntry"("transaction_id");

CREATE TABLE "JournalLine" (
    "id" TEXT NOT NULL,
    "journal_entry_id" TEXT NOT NULL,
    "ledger_account_id" TEXT NOT NULL,
    "side" "LedgerSide" NOT NULL,
    "amount" DECIMAL(18,2) NOT NULL,
    "internal_account_id" TEXT,
    CONSTRAINT "JournalLine_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "JournalLine_journal_entry_id_idx" ON "JournalLine"("journal_entry_id");
CREATE INDEX "JournalLine_ledger_account_id_idx" ON "JournalLine"("ledger_account_id");

ALTER TABLE "JournalEntry" ADD CONSTRAINT "JournalEntry_transaction_id_fkey" FOREIGN KEY ("transaction_id") REFERENCES "Transaction"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "JournalLine" ADD CONSTRAINT "JournalLine_journal_entry_id_fkey" FOREIGN KEY ("journal_entry_id") REFERENCES "JournalEntry"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "JournalLine" ADD CONSTRAINT "JournalLine_ledger_account_id_fkey" FOREIGN KEY ("ledger_account_id") REFERENCES "LedgerAccount"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "JournalLine" ADD CONSTRAINT "JournalLine_internal_account_id_fkey" FOREIGN KEY ("internal_account_id") REFERENCES "Account"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Payment instructions
CREATE TABLE "PaymentInstruction" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "from_account_id" TEXT NOT NULL,
    "amount" DECIMAL(18,2) NOT NULL,
    "rail" "PaymentRail" NOT NULL,
    "counterparty" JSONB,
    "status" "PaymentInstructionStatus" NOT NULL DEFAULT 'PENDING',
    "idempotency_key" TEXT NOT NULL,
    "reference" TEXT,
    "failure_reason" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "PaymentInstruction_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "PaymentInstruction_idempotency_key_key" ON "PaymentInstruction"("idempotency_key");
CREATE INDEX "PaymentInstruction_user_id_idx" ON "PaymentInstruction"("user_id");
CREATE INDEX "PaymentInstruction_status_idx" ON "PaymentInstruction"("status");
ALTER TABLE "PaymentInstruction" ADD CONSTRAINT "PaymentInstruction_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "PaymentInstruction" ADD CONSTRAINT "PaymentInstruction_from_account_id_fkey" FOREIGN KEY ("from_account_id") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Card authorizations
CREATE TABLE "CardAuthorization" (
    "id" TEXT NOT NULL,
    "card_id" TEXT NOT NULL,
    "amount" DECIMAL(18,2) NOT NULL,
    "merchant_name" TEXT,
    "status" "CardAuthorizationStatus" NOT NULL DEFAULT 'AUTHORIZED',
    "idempotency_key" TEXT NOT NULL,
    "capture_txn_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "CardAuthorization_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "CardAuthorization_idempotency_key_key" ON "CardAuthorization"("idempotency_key");
CREATE INDEX "CardAuthorization_card_id_idx" ON "CardAuthorization"("card_id");
CREATE INDEX "CardAuthorization_status_idx" ON "CardAuthorization"("status");
ALTER TABLE "CardAuthorization" ADD CONSTRAINT "CardAuthorization_card_id_fkey" FOREIGN KEY ("card_id") REFERENCES "Card"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Loan installments
CREATE TABLE "LoanInstallment" (
    "id" TEXT NOT NULL,
    "loan_id" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "due_date" TIMESTAMP(3) NOT NULL,
    "amount_due" DECIMAL(18,2) NOT NULL,
    "principal_part" DECIMAL(18,2) NOT NULL,
    "interest_part" DECIMAL(18,2) NOT NULL,
    "status" "LoanInstallmentStatus" NOT NULL DEFAULT 'PENDING',
    "paid_at" TIMESTAMP(3),
    CONSTRAINT "LoanInstallment_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "LoanInstallment_loan_id_sequence_key" ON "LoanInstallment"("loan_id", "sequence");
CREATE INDEX "LoanInstallment_loan_id_idx" ON "LoanInstallment"("loan_id");
CREATE INDEX "LoanInstallment_due_date_idx" ON "LoanInstallment"("due_date");
ALTER TABLE "LoanInstallment" ADD CONSTRAINT "LoanInstallment_loan_id_fkey" FOREIGN KEY ("loan_id") REFERENCES "Loan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Account holds
CREATE TABLE "AccountHold" (
    "id" TEXT NOT NULL,
    "account_id" TEXT NOT NULL,
    "amount" DECIMAL(18,2) NOT NULL,
    "reason" TEXT NOT NULL,
    "released_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "AccountHold_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "AccountHold_account_id_idx" ON "AccountHold"("account_id");
ALTER TABLE "AccountHold" ADD CONSTRAINT "AccountHold_account_id_fkey" FOREIGN KEY ("account_id") REFERENCES "Account"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Pending admin actions
CREATE TABLE "PendingAdminAction" (
    "id" TEXT NOT NULL,
    "action_type" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "status" "PendingAdminActionStatus" NOT NULL DEFAULT 'PENDING',
    "maker_id" TEXT NOT NULL,
    "checker_id" TEXT,
    "resolution_note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolved_at" TIMESTAMP(3),
    CONSTRAINT "PendingAdminAction_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "PendingAdminAction_status_idx" ON "PendingAdminAction"("status");
ALTER TABLE "PendingAdminAction" ADD CONSTRAINT "PendingAdminAction_maker_id_fkey" FOREIGN KEY ("maker_id") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "PendingAdminAction" ADD CONSTRAINT "PendingAdminAction_checker_id_fkey" FOREIGN KEY ("checker_id") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- Support cases
CREATE TABLE "SupportCase" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "subject" TEXT NOT NULL,
    "body" TEXT,
    "status" "SupportCaseStatus" NOT NULL DEFAULT 'OPEN',
    "priority" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "SupportCase_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "SupportCase_user_id_idx" ON "SupportCase"("user_id");
CREATE INDEX "SupportCase_status_idx" ON "SupportCase"("status");
ALTER TABLE "SupportCase" ADD CONSTRAINT "SupportCase_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- KYB
CREATE TABLE "BusinessProfile" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "company_name" TEXT NOT NULL,
    "registration_number" TEXT,
    "country" TEXT NOT NULL DEFAULT 'US',
    "status" "KybStatus" NOT NULL DEFAULT 'PENDING',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "BusinessProfile_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "BusinessProfile_user_id_key" ON "BusinessProfile"("user_id");
ALTER TABLE "BusinessProfile" ADD CONSTRAINT "BusinessProfile_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Screening
CREATE TABLE "ScreeningCheck" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "pep_hit" BOOLEAN NOT NULL DEFAULT false,
    "sanctions_hit" BOOLEAN NOT NULL DEFAULT false,
    "status" "ScreeningResultStatus" NOT NULL DEFAULT 'CLEAR',
    "notes" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ScreeningCheck_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ScreeningCheck_user_id_idx" ON "ScreeningCheck"("user_id");
ALTER TABLE "ScreeningCheck" ADD CONSTRAINT "ScreeningCheck_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Data export
CREATE TABLE "DataExportRequest" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "status" "DataExportStatus" NOT NULL DEFAULT 'REQUESTED',
    "result_json" JSONB,
    "error_message" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP(3),
    CONSTRAINT "DataExportRequest_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "DataExportRequest_user_id_idx" ON "DataExportRequest"("user_id");
CREATE INDEX "DataExportRequest_status_idx" ON "DataExportRequest"("status");
ALTER TABLE "DataExportRequest" ADD CONSTRAINT "DataExportRequest_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Webhook deliveries
CREATE TABLE "WebhookDelivery" (
    "id" TEXT NOT NULL,
    "webhook_endpoint_id" TEXT NOT NULL,
    "event_type" TEXT NOT NULL,
    "body" JSONB NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "attempt_count" INTEGER NOT NULL DEFAULT 0,
    "last_error" TEXT,
    "next_attempt_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "WebhookDelivery_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "WebhookDelivery_status_idx" ON "WebhookDelivery"("status");
CREATE INDEX "WebhookDelivery_webhook_endpoint_id_idx" ON "WebhookDelivery"("webhook_endpoint_id");
ALTER TABLE "WebhookDelivery" ADD CONSTRAINT "WebhookDelivery_webhook_endpoint_id_fkey" FOREIGN KEY ("webhook_endpoint_id") REFERENCES "WebhookEndpoint"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- Seed GL accounts (fixed IDs for app constants)
INSERT INTO "LedgerAccount" ("id", "code", "name", "type", "created_at", "updated_at") VALUES
('11111111-1111-1111-1111-111111111101', '1000', 'Bank clearing (asset)', 'ASSET', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('11111111-1111-1111-1111-111111111102', '2100', 'Customer deposits (liability pool)', 'LIABILITY', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT ("code") DO NOTHING;
