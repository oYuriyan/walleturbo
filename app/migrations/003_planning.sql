-- Planejamento e orçamentos mensais, sem alterar registros financeiros.

CREATE TABLE month_plans (
	owner VARCHAR(128) NOT NULL,
	month VARCHAR(7) NOT NULL,
	income_reference_cents BIGINT,
	buffer_cents BIGINT NOT NULL,
	records_complete BOOLEAN NOT NULL,
 stats_signature VARCHAR(64),
	PRIMARY KEY (owner, month),
	CHECK (income_reference_cents IS NULL OR income_reference_cents BETWEEN 1 AND 99999999999),
	CHECK (buffer_cents BETWEEN 0 AND 99999999999)
)
;

CREATE TABLE budgets (
	owner VARCHAR(128) NOT NULL,
	month VARCHAR(7) NOT NULL,
	category VARCHAR(40) NOT NULL,
	amount_cents BIGINT NOT NULL,
	PRIMARY KEY (owner, month, category),
	CHECK (amount_cents BETWEEN 1 AND 99999999999)
)
;
