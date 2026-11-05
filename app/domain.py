import csv
import hashlib
import io
import re
from collections import defaultdict
from datetime import date, date as CivilDate
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CATEGORIES = (
    "Moradia",
    "Alimentação",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Assinaturas",
    "Compras",
    "Renda",
    "Outros",
)


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    date: CivilDate = Field(ge=CivilDate(1900, 1, 1), le=CivilDate(9998, 12, 31))
    description: str = Field(min_length=1, max_length=160)
    amount_cents: int = Field(strict=True, gt=0, le=99999999999)
    kind: Literal["income", "expense"] = "expense"
    category: str = "Outros"
    reviewed: bool = False
    account_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value not in CATEGORIES:
            raise ValueError("Categoria inválida")
        return value


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    target_cents: int = Field(strict=True, gt=0, le=99999999999)
    saved_cents: int = Field(strict=True, ge=0, le=99999999999)
    deadline: date

    @model_validator(mode="after")
    def valid_saved(self):
        if self.saved_cents > self.target_cents:
            raise ValueError("Reserva não pode superar a meta")
        return self


def suggest_category(description):
    text = description.casefold()
    for category, words in {
        "Alimentação": ("mercado", "restaurante", "ifood", "padaria"),
        "Transporte": ("uber", "combustível", "posto", "99app"),
        "Assinaturas": ("netflix", "spotify", "assinatura"),
        "Saúde": ("farmácia", "hospital", "consulta"),
    }.items():
        if any(word in text for word in words):
            return category
    return "Outros"


def parse_csv(content: str):
    if len(content.encode("utf-8")) > 256_000:
        raise ValueError("Arquivo excede 256 KB")
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter=";")
    if reader.fieldnames != ["data", "descricao", "valor", "tipo"]:
        raise ValueError("Cabeçalho esperado: data;descricao;valor;tipo")
    entries = []
    for number, row in enumerate(reader, 2):
        if number > 501:
            raise ValueError("Limite de 500 lançamentos por arquivo")
        try:
            value = row["valor"].strip()
            if not re.fullmatch(r"\d{1,9},\d{2}", value):
                raise ValueError()
            cents = int(Decimal(value.replace(",", ".")) * 100)
            kind = {"despesa": "expense", "receita": "income"}[row["tipo"].strip()]
            entries.append(
                Entry(
                    date=row["data"],
                    description=row["descricao"],
                    amount_cents=cents,
                    kind=kind,
                    category=(
                        "Renda"
                        if kind == "income"
                        else suggest_category(row["descricao"])
                    ),
                )
            )
        except (ValueError, KeyError, TypeError, AttributeError, InvalidOperation):
            raise ValueError(
                f"Linha {number} inválida; use data AAAA-MM-DD, valor 123,45 e tipo despesa/receita"
            ) from None
    if not entries:
        raise ValueError("Arquivo sem lançamentos")
    return entries


def import_keys(entries):
    # A contagem de ocorrências preserva compras iguais legítimas no mesmo arquivo.
    occurrences = defaultdict(int)
    result = []
    for entry in entries:
        canonical = f"{entry.date}|{entry.description.casefold()}|{entry.amount_cents}|{entry.kind}"
        occurrences[canonical] += 1
        result.append(
            hashlib.sha256(f"{canonical}|{occurrences[canonical]}".encode()).hexdigest()
        )
    return result


def summarize(entries):
    income = sum(e.amount_cents for e in entries if e.kind == "income")
    expenses = sum(e.amount_cents for e in entries if e.kind == "expense")
    categories = defaultdict(int)
    for entry in entries:
        if entry.kind == "expense":
            categories[entry.category] += entry.amount_cents
    insights = []
    subscriptions = categories.get("Assinaturas", 0)
    if subscriptions:
        insights.append(
            {
                "title": "Revise suas assinaturas",
                "description": "Confira quais serviços ainda são úteis. O valor indica gastos na categoria, não economia garantida.",
                "amount_cents": subscriptions,
            }
        )
    if expenses > income:
        insights.append(
            {
                "title": "Saídas acima das entradas",
                "description": "Neste mês, as despesas registradas superam as receitas. Confira se todas as entradas foram lançadas.",
                "amount_cents": expenses - income,
            }
        )
    return {
        "income_cents": income,
        "expense_cents": expenses,
        "balance_cents": income - expenses,
        "categories": dict(categories),
        "pending": sum(not e.reviewed for e in entries),
        "insights": insights,
    }
