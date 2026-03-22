-- CreateEnum
CREATE TYPE "RecurringFrequency" AS ENUM ('WEEKLY', 'MONTHLY');

-- CreateEnum
CREATE TYPE "CardStatus" AS ENUM ('ACTIVE', 'CANCELLED');

-- AlterTable User
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "phone" TEXT;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "notify_email" BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "notify_push" BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "daily_transfer_max" DECIMAL(18,2);
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "daily_atm_max" DECIMAL(18,2);

-- AlterTable Account
ALTER TABLE "Account" ADD COLUMN IF NOT EXISTS "nickname" TEXT;
ALTER TABLE "Account" ADD COLUMN IF NOT EXISTS "is_frozen" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable Transaction
ALTER TABLE "Transaction" ADD COLUMN IF NOT EXISTS "client_reference" TEXT;

-- AlterTable AuditLog
ALTER TABLE "AuditLog" ADD COLUMN IF NOT EXISTS "read_at" TIMESTAMP(3);

-- CreateTable RefreshToken
CREATE TABLE IF NOT EXISTS "RefreshToken" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "token_hash" TEXT NOT NULL,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "user_agent" TEXT,
    "ip_address" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RefreshToken_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "RefreshToken_token_hash_key" ON "RefreshToken"("token_hash");
CREATE INDEX IF NOT EXISTS "RefreshToken_user_id_idx" ON "RefreshToken"("user_id");
ALTER TABLE "RefreshToken" ADD CONSTRAINT "RefreshToken_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable PasswordResetToken
CREATE TABLE IF NOT EXISTS "PasswordResetToken" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "token_hash" TEXT NOT NULL,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "used_at" TIMESTAMP(3),
    CONSTRAINT "PasswordResetToken_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "PasswordResetToken_token_hash_key" ON "PasswordResetToken"("token_hash");
CREATE INDEX IF NOT EXISTS "PasswordResetToken_user_id_idx" ON "PasswordResetToken"("user_id");
ALTER TABLE "PasswordResetToken" ADD CONSTRAINT "PasswordResetToken_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable LoanProduct
CREATE TABLE IF NOT EXISTS "LoanProduct" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "min_principal" DECIMAL(18,2) NOT NULL,
    "max_principal" DECIMAL(18,2) NOT NULL,
    "min_tenure_months" INTEGER NOT NULL,
    "max_tenure_months" INTEGER NOT NULL,
    "annual_rate_pct" DECIMAL(8,4) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "LoanProduct_pkey" PRIMARY KEY ("id")
);

-- CreateTable RecurringPayment
CREATE TABLE IF NOT EXISTS "RecurringPayment" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "from_account_id" TEXT NOT NULL,
    "to_account_id" TEXT NOT NULL,
    "amount" DECIMAL(18,2) NOT NULL,
    "frequency" "RecurringFrequency" NOT NULL,
    "next_run_at" TIMESTAMP(3) NOT NULL,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "description" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "RecurringPayment_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "RecurringPayment_user_id_idx" ON "RecurringPayment"("user_id");
CREATE INDEX IF NOT EXISTS "RecurringPayment_next_run_at_idx" ON "RecurringPayment"("next_run_at");
ALTER TABLE "RecurringPayment" ADD CONSTRAINT "RecurringPayment_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "RecurringPayment" ADD CONSTRAINT "RecurringPayment_from_account_id_fkey" FOREIGN KEY ("from_account_id") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "RecurringPayment" ADD CONSTRAINT "RecurringPayment_to_account_id_fkey" FOREIGN KEY ("to_account_id") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- CreateTable Beneficiary
CREATE TABLE IF NOT EXISTS "Beneficiary" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "display_name" TEXT NOT NULL,
    "beneficiary_account_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Beneficiary_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "Beneficiary_user_id_idx" ON "Beneficiary"("user_id");
ALTER TABLE "Beneficiary" ADD CONSTRAINT "Beneficiary_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Beneficiary" ADD CONSTRAINT "Beneficiary_beneficiary_account_id_fkey" FOREIGN KEY ("beneficiary_account_id") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- CreateTable Card
CREATE TABLE IF NOT EXISTS "Card" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "last4" TEXT NOT NULL,
    "status" "CardStatus" NOT NULL DEFAULT 'ACTIVE',
    "is_frozen" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Card_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "Card_user_id_idx" ON "Card"("user_id");
ALTER TABLE "Card" ADD CONSTRAINT "Card_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- CreateTable WebhookEndpoint
CREATE TABLE IF NOT EXISTS "WebhookEndpoint" (
    "id" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "secret" TEXT,
    "events" JSONB,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "WebhookEndpoint_pkey" PRIMARY KEY ("id")
);

-- CreateTable ApiKey
CREATE TABLE IF NOT EXISTS "ApiKey" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "key_hash" TEXT NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_used_at" TIMESTAMP(3),
    CONSTRAINT "ApiKey_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "ApiKey_key_hash_key" ON "ApiKey"("key_hash");

-- Seed loan products (fixed UUIDs for idempotent docs)
INSERT INTO "LoanProduct" ("id","name","min_principal","max_principal","min_tenure_months","max_tenure_months","annual_rate_pct","created_at")
VALUES
  ('lp_personal_01','Personal Flex',5000,100000,12,84,11.4900,NOW()),
  ('lp_home_01','Home Advantage',25000,2000000,60,360,7.2500,NOW()),
  ('lp_auto_01','Auto Drive',3000,150000,12,72,9.9900,NOW())
ON CONFLICT ("id") DO NOTHING;
