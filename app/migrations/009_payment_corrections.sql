-- Pagamentos legados mantêm conta, data, valor, UUID e ID.
ALTER TABLE statement_payments ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE statement_payments ADD COLUMN correction_reason VARCHAR(160);
