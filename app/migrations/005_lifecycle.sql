-- Cadastros existentes permanecem ativos. Nenhum vínculo financeiro é removido.
ALTER TABLE accounts ADD COLUMN archived BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE accounts ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cards ADD COLUMN archived BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE cards ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
