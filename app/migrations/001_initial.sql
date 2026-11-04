-- Migração inicial. Executada apenas em um volume PostgreSQL novo pelo Compose.
CREATE TABLE transactions (
 id varchar(36) PRIMARY KEY, owner varchar(128) NOT NULL, date date NOT NULL,
 description varchar(160) NOT NULL, amount_cents bigint NOT NULL CHECK (amount_cents > 0 AND amount_cents <= 99999999999),
 kind varchar(10) NOT NULL CHECK (kind IN ('income', 'expense')),
 category varchar(40) NOT NULL, reviewed boolean NOT NULL DEFAULT false, import_key varchar(64)
);
CREATE INDEX ix_transaction_owner_date ON transactions(owner,date);
CREATE UNIQUE INDEX ix_import_owner ON transactions(owner,import_key);
CREATE TABLE goals (
 id varchar(36) PRIMARY KEY, owner varchar(128) NOT NULL, name varchar(100) NOT NULL,
 target_cents bigint NOT NULL, saved_cents bigint NOT NULL, deadline date NOT NULL,
 CHECK (target_cents > 0 AND saved_cents >= 0 AND saved_cents <= target_cents)
);
CREATE INDEX ix_goals_owner ON goals(owner);
