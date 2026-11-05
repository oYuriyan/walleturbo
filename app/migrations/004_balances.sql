-- Referências com histórico e transferências; contas antigas permanecem sem saldo presumido.

CREATE TABLE opening_balances (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	account_id VARCHAR(36) NOT NULL,
	date DATE NOT NULL,
	amount_cents BIGINT NOT NULL,
	version INTEGER NOT NULL,
	reason VARCHAR(160) NOT NULL,
	request_id VARCHAR(36) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(owner, account_id) REFERENCES accounts (owner, id),
	UNIQUE (owner, request_id),
	UNIQUE (owner, account_id, version),
	CHECK (amount_cents BETWEEN -99999999999 AND 99999999999),
	CHECK (version > 0)
)

;

CREATE TABLE transfers (
	id VARCHAR(36) NOT NULL,
	owner VARCHAR(128) NOT NULL,
	source_account_id VARCHAR(36) NOT NULL,
	destination_account_id VARCHAR(36) NOT NULL,
	date DATE NOT NULL,
	amount_cents BIGINT NOT NULL,
	description VARCHAR(160) NOT NULL,
	request_id VARCHAR(36) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	reversed_date DATE,
	PRIMARY KEY (id),
	FOREIGN KEY(owner, source_account_id) REFERENCES accounts (owner, id),
	FOREIGN KEY(owner, destination_account_id) REFERENCES accounts (owner, id),
	UNIQUE (owner, request_id),
	CHECK (amount_cents BETWEEN 1 AND 99999999999),
	CHECK (source_account_id <> destination_account_id),
	CHECK (reversed_date IS NULL OR reversed_date >= date)
)

;
CREATE INDEX ix_transfer_owner_date ON transfers (owner, date);
