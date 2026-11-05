ALTER TABLE transactions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE transactions ADD COLUMN request_id VARCHAR(36);
ALTER TABLE transactions ADD COLUMN correction_reason VARCHAR(160);
ALTER TABLE transactions ADD CONSTRAINT uq_transaction_owner_request UNIQUE(owner,request_id);
CREATE TABLE import_marks (
    owner VARCHAR(128) NOT NULL,
    scope VARCHAR(16) NOT NULL,
    container_id VARCHAR(36) NOT NULL,
    source_key VARCHAR(64) NOT NULL,
    resource_id VARCHAR(36),
    removed BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY(owner,scope,container_id,source_key)
);
INSERT INTO import_marks(owner,scope,container_id,source_key,resource_id)
SELECT owner,'transaction','',import_key,id FROM transactions WHERE import_key IS NOT NULL;
INSERT INTO import_marks(owner,scope,container_id,source_key,resource_id)
SELECT owner,'card',statement_id,import_key,id FROM card_charges WHERE import_key IS NOT NULL;
-- Eventos anteriores não guardam a chave de origem; não inferir identidades excluídas.
