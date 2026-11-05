-- Metas existentes permanecem ativas, com valores e prazos preservados.
ALTER TABLE goals ADD COLUMN archived BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE goals ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
