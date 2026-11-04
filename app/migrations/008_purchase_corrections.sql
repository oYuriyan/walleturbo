ALTER TABLE card_charges ADD COLUMN correction_reason VARCHAR(160);
ALTER TABLE card_charges ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
CREATE TABLE request_receipts (
    owner VARCHAR(128) NOT NULL,
    scope VARCHAR(24) NOT NULL,
    request_id VARCHAR(36) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    resource_id VARCHAR(36),
    cancelled BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (owner,scope,request_id)
);
INSERT INTO request_receipts(owner,scope,request_id,payload_hash,resource_id)
SELECT DISTINCT owner,'purchase',operation_id,payload_hash,operation_id
FROM card_charges WHERE import_key IS NULL;
INSERT INTO request_receipts(owner,scope,request_id,payload_hash,resource_id)
SELECT owner,'payment',request_id,payload_hash,id FROM statement_payments;
-- Estados excluídos auditados desde 0.8: reservar o UUID sem inventar o hash ausente.
INSERT INTO request_receipts(owner,scope,request_id,payload_hash,resource_id,cancelled)
SELECT DISTINCT owner,'purchase',"before"->>'operation_id',repeat('0',64),"before"->>'operation_id',true
FROM financial_audit WHERE entity='card_charge' AND action='deleted' AND "before"->>'operation_id' IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO request_receipts(owner,scope,request_id,payload_hash,resource_id,cancelled)
SELECT DISTINCT owner,'payment',"before"->>'request_id',repeat('0',64),"before"->>'id',true
FROM financial_audit WHERE entity='statement_payment' AND action='deleted' AND "before"->>'request_id' IS NOT NULL
ON CONFLICT DO NOTHING;
