from datetime import date
from uuid import uuid4
from sqlalchemy import (
    BigInteger,
    Date,
    String,
    Boolean,
    Index,
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
    Integer,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.config import settings


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(40))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    import_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner", "account_id"], ["accounts.owner", "accounts.id"]
        ),
        Index("ix_transaction_owner_date", "owner", "date"),
        Index("ix_import_owner", "owner", "import_key", unique=True),
        CheckConstraint("amount_cents > 0 AND amount_cents <= 99999999999"),
        CheckConstraint("kind IN ('income', 'expense')"),
    )


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(100))
    target_cents: Mapped[int] = mapped_column(BigInteger)
    saved_cents: Mapped[int] = mapped_column(BigInteger)
    deadline: Mapped[date] = mapped_column(Date)
    __table_args__ = (
        CheckConstraint(
            "target_cents > 0 AND saved_cents >= 0 AND saved_cents <= target_cents"
        ),
    )


# Chaves compostas impedem associações entre proprietários também no banco.


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("owner", "id"),)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(80))
    due_day: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("owner", "id"),
        CheckConstraint("due_day BETWEEN 1 AND 31"),
    )


class Statement(Base):
    __tablename__ = "statements"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128))
    card_id: Mapped[str] = mapped_column(String(36))
    month: Mapped[str] = mapped_column(String(7))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="open")
    expected_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    __table_args__ = (
        UniqueConstraint("owner", "id"),
        UniqueConstraint("owner", "card_id", "month"),
        ForeignKeyConstraint(["owner", "card_id"], ["cards.owner", "cards.id"]),
        CheckConstraint("status IN ('open', 'closed')"),
        CheckConstraint(
            "expected_cents IS NULL OR expected_cents BETWEEN 0 AND 99999999999"
        ),
    )


class Charge(Base):
    __tablename__ = "card_charges"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128))
    statement_id: Mapped[str] = mapped_column(String(36))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(40))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    operation_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    installment: Mapped[int] = mapped_column(Integer)
    installments: Mapped[int] = mapped_column(Integer)
    import_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner", "statement_id"], ["statements.owner", "statements.id"]
        ),
        UniqueConstraint("owner", "operation_id", "installment"),
        UniqueConstraint("owner", "statement_id", "import_key"),
        Index("ix_charge_statement", "owner", "statement_id"),
        CheckConstraint("amount_cents BETWEEN 1 AND 99999999999"),
        CheckConstraint("kind IN ('expense', 'refund')"),
        CheckConstraint(
            "installments BETWEEN 1 AND 36 AND installment BETWEEN 1 AND installments"
        ),
    )


class StatementPayment(Base):
    __tablename__ = "statement_payments"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner: Mapped[str] = mapped_column(String(128))
    statement_id: Mapped[str] = mapped_column(String(36))
    account_id: Mapped[str] = mapped_column(String(36))
    date: Mapped[date] = mapped_column(Date)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    request_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner", "statement_id"], ["statements.owner", "statements.id"]
        ),
        ForeignKeyConstraint(
            ["owner", "account_id"], ["accounts.owner", "accounts.id"]
        ),
        UniqueConstraint("owner", "request_id"),
        CheckConstraint("amount_cents BETWEEN 1 AND 99999999999"),
        Index("ix_payment_owner_date", "owner", "date"),
    )


engine = create_engine(settings().database_url, pool_pre_ping=True)
Session = sessionmaker(engine)


def db_session():
    with Session() as session:
        yield session
