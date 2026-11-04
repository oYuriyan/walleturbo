from datetime import date
from uuid import uuid4
from sqlalchemy import BigInteger, Date, String, Boolean, Index, CheckConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.config import settings


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner: Mapped[str] = mapped_column(String(128))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(40))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    import_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        Index("ix_transaction_owner_date", "owner", "date"),
        Index("ix_import_owner", "owner", "import_key", unique=True),
        CheckConstraint("amount_cents > 0 AND amount_cents <= 99999999999"),
        CheckConstraint("kind IN ('income', 'expense')"),
    )


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(100))
    target_cents: Mapped[int] = mapped_column(BigInteger)
    saved_cents: Mapped[int] = mapped_column(BigInteger)
    deadline: Mapped[date] = mapped_column(Date)
    __table_args__ = (CheckConstraint("target_cents > 0 AND saved_cents >= 0 AND saved_cents <= target_cents"),)


engine = create_engine(settings().database_url, pool_pre_ping=True)
Session = sessionmaker(engine)


def db_session():
    with Session() as session:
        yield session
