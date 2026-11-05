-- Contas, cartões, parcelas e pagamentos. Sem conversão implícita do histórico.

CREATE TABLE accounts (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	name VARCHAR(80) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (owner, id)
)

;
CREATE INDEX ix_accounts_owner ON accounts (owner);

CREATE TABLE cards (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	name VARCHAR(80) NOT NULL,
	due_day INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (owner, id),
	CHECK (due_day BETWEEN 1 AND 31)
)

;
CREATE INDEX ix_cards_owner ON cards (owner);

CREATE TABLE statements (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	card_id VARCHAR(36) NOT NULL,
	month VARCHAR(7) NOT NULL,
	due_date DATE NOT NULL,
	status VARCHAR(10) NOT NULL,
	expected_cents BIGINT,
	PRIMARY KEY (id),
	UNIQUE (owner, id),
	UNIQUE (owner, card_id, month),
	FOREIGN KEY(owner, card_id) REFERENCES cards (owner, id),
	CHECK (status IN ('open', 'closed')),
	CHECK (expected_cents IS NULL OR expected_cents BETWEEN 0 AND 99999999999)
)

;

CREATE TABLE card_charges (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	statement_id VARCHAR(36) NOT NULL,
	date DATE NOT NULL,
	description VARCHAR(160) NOT NULL,
	amount_cents BIGINT NOT NULL,
	kind VARCHAR(10) NOT NULL,
	category VARCHAR(40) NOT NULL,
	reviewed BOOLEAN NOT NULL,
	operation_id VARCHAR(36) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	installment INTEGER NOT NULL,
	installments INTEGER NOT NULL,
	import_key VARCHAR(64),
	PRIMARY KEY (id),
	FOREIGN KEY(owner, statement_id) REFERENCES statements (owner, id),
	UNIQUE (owner, operation_id, installment),
	UNIQUE (owner, statement_id, import_key),
	CHECK (amount_cents BETWEEN 1 AND 99999999999),
	CHECK (kind IN ('expense', 'refund')),
	CHECK (installments BETWEEN 1 AND 36 AND installment BETWEEN 1 AND installments)
)

;
CREATE INDEX ix_charge_statement ON card_charges (owner, statement_id);

CREATE TABLE statement_payments (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	statement_id VARCHAR(36) NOT NULL,
	account_id VARCHAR(36) NOT NULL,
	date DATE NOT NULL,
	amount_cents BIGINT NOT NULL,
	request_id VARCHAR(36) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(owner, statement_id) REFERENCES statements (owner, id),
	FOREIGN KEY(owner, account_id) REFERENCES accounts (owner, id),
	UNIQUE (owner, request_id),
	CHECK (amount_cents BETWEEN 1 AND 99999999999)
)

;
CREATE INDEX ix_payment_owner_date ON statement_payments (owner, date);
ALTER TABLE transactions ADD COLUMN account_id varchar(36);
ALTER TABLE transactions ADD CONSTRAINT fk_transaction_account FOREIGN KEY (owner, account_id) REFERENCES accounts(owner, id);
