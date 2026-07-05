-- ============================================================
-- Migration v2 — Banking API → Supabase
-- À exécuter dans le SQL Editor Supabase
-- ============================================================

-- Table users (authentification)
CREATE TABLE IF NOT EXISTS users (
  id            UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  username      TEXT    NOT NULL UNIQUE,
  password_hash TEXT    NOT NULL,
  email         TEXT    UNIQUE,
  role          TEXT    NOT NULL DEFAULT 'CLIENT' CHECK (role IN ('CLIENT', 'ADMIN')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Table comptes (v2 : + type, status, overdraft_limit, annual_rate)
CREATE TABLE IF NOT EXISTS comptes (
  id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  numero_compte  TEXT         NOT NULL UNIQUE,
  nom_titulaire  TEXT         NOT NULL,
  email          TEXT         NOT NULL,
  solde          NUMERIC(14,2) NOT NULL DEFAULT 0,
  type           TEXT         NOT NULL DEFAULT 'CURRENT' CHECK (type IN ('CURRENT', 'SAVINGS')),
  status         TEXT         NOT NULL DEFAULT 'ACTIVE'  CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED')),
  overdraft_limit NUMERIC(14,2) NOT NULL DEFAULT 0,
  annual_rate    NUMERIC(6,4)  NOT NULL DEFAULT 0,
  date_creation  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Table transactions
CREATE TABLE IF NOT EXISTS transactions (
  id                  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  type                TEXT    NOT NULL CHECK (type IN ('depot', 'retrait', 'virement')),
  montant             NUMERIC(14,2) NOT NULL,
  date                TIMESTAMPTZ   NOT NULL DEFAULT now(),
  compte_source       TEXT    NOT NULL REFERENCES comptes(numero_compte) ON DELETE CASCADE,
  compte_destination  TEXT    REFERENCES comptes(numero_compte) ON DELETE SET NULL
);

-- Index de performance
CREATE INDEX IF NOT EXISTS idx_comptes_numero    ON comptes(numero_compte);
CREATE INDEX IF NOT EXISTS idx_comptes_email     ON comptes(email);
CREATE INDEX IF NOT EXISTS idx_comptes_status    ON comptes(status);
CREATE INDEX IF NOT EXISTS idx_transactions_src  ON transactions(compte_source);
CREATE INDEX IF NOT EXISTS idx_transactions_dst  ON transactions(compte_destination);
CREATE INDEX IF NOT EXISTS idx_users_username    ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email       ON users(email);

-- Row Level Security
ALTER TABLE comptes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE users        ENABLE ROW LEVEL SECURITY;

-- Policies : l'API utilise service_role → bypass RLS
CREATE POLICY "service_role_comptes"      ON comptes      FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_transactions" ON transactions  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_users"        ON users         FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Seed : admin par défaut (mot de passe : admin123 — À CHANGER en production !)
-- Le hash bcrypt ci-dessous correspond à "admin123"
INSERT INTO users (username, password_hash, role)
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY.5aExxx/example', 'ADMIN')
ON CONFLICT (username) DO NOTHING;
