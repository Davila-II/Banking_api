-- Migration: Banking API → Supabase
-- À exécuter dans le SQL Editor Supabase (https://supabase.com/dashboard)

-- Table des comptes
CREATE TABLE IF NOT EXISTS comptes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  numero_compte TEXT NOT NULL UNIQUE,
  nom_titulaire TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  solde NUMERIC(12,2) NOT NULL DEFAULT 0,
  date_creation TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Table des transactions
CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL CHECK (type IN ('depot', 'retrait', 'virement')),
  montant NUMERIC(12,2) NOT NULL,
  date TIMESTAMPTZ NOT NULL DEFAULT now(),
  compte_source TEXT NOT NULL REFERENCES comptes(numero_compte) ON DELETE CASCADE,
  compte_destination TEXT REFERENCES comptes(numero_compte) ON DELETE SET NULL
);

-- Index pour les recherches fréquentes
CREATE INDEX IF NOT EXISTS idx_comptes_numero ON comptes(numero_compte);
CREATE INDEX IF NOT EXISTS idx_comptes_email ON comptes(email);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(compte_source);
CREATE INDEX IF NOT EXISTS idx_transactions_dest ON transactions(compte_destination);

-- Enable RLS (Row Level Security)
ALTER TABLE comptes ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Policies: service_role bypass RLS (l'API utilise la clé service_role)
-- Pour la clé anon, on bloque tout
CREATE POLICY "service_role_full_access_comptes" ON comptes FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_full_access_transactions" ON transactions FOR ALL TO service_role USING (true) WITH CHECK (true);
