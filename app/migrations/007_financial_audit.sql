-- Sem backfill: não é possível reconstruir estados anteriores que não foram guardados.
CREATE TABLE financial_audit (
    id VARCHAR(36) PRIMARY KEY,
    owner VARCHAR(128) NOT NULL,
    entity VARCHAR(32) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    action VARCHAR(16) NOT NULL CHECK (action IN ('created','updated','deleted')),
    occurred_at VARCHAR(32) NOT NULL,
    before JSON,
    after JSON
);
CREATE INDEX ix_financial_audit_owner_time ON financial_audit(owner, occurred_at, id);
