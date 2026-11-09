"""Extração explícita e revisão de candidatos; nunca lança PDF automaticamente."""

import hashlib
import json
import re
import secrets
from datetime import date
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app import security
from app.cards import (
    owned,
    require_open,
    lock_statement,
    ReviewInput,
    active_statement_card,
)
from app.db import Statement, Charge, db_session
from app.import_marks import reserve, result as import_result
from app.domain import suggest_category
from app.pdf_protocol import MAX_PDF_BYTES, extract_isolated

router = APIRouter(prefix="/api/statements")
PREVIEW_TTL = 600
ERRORS = {
    "invalid_pdf": "PDF inválido ou não suportado. Use um arquivo original com texto selecionável.",
    "encrypted": "PDF protegido por senha não é aceito nesta etapa.",
    "active_content": "PDF com ações, formulários, links ativos ou anexos não é aceito nesta etapa.",
    "too_many_pages": "PDF excede o limite de 30 páginas.",
    "too_complex": "PDF excedeu os limites de processamento. Exporte um CSV ou um PDF menor.",
    "ocr_required": "Não foi encontrado texto selecionável. PDFs escaneados ainda exigem OCR, não disponível nesta versão.",
}
LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\s+(.+?)\s+(?:R\$\s*)?(-?(?:\d{1,3}(?:\.\d{3})+|\d{1,9}),\d{2})$"
)
PAN = re.compile(r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)")


class ExtractedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(strict=True, ge=1, le=30)
    text: str = Field(max_length=100000)


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pages: list[ExtractedPage] = Field(min_length=1, max_length=30)
    empty_pages: list[int] = Field(max_length=30)


def candidates(payload):
    entries, skipped = [], 0
    for page in payload["pages"]:
        for line_number, raw in enumerate(page["text"].splitlines(), 1):
            line = " ".join(raw.split())
            if not line:
                continue
            match = LINE.fullmatch(line)
            if not match:
                skipped += 1
                continue
            raw_date, description, raw_value = match.groups()
            if re.match(r"(?i)^(total|saldo|pagamento|limite)\b", description):
                skipped += 1
                continue
            try:
                parsed_date = date.fromisoformat(
                    raw_date
                    if "-" in raw_date
                    else "-".join(reversed(raw_date.split("/")))
                )
            except ValueError:
                skipped += 1
                continue
            amount = int(raw_value.replace(".", "").replace(",", ""))
            description = PAN.sub("[número oculto]", description).strip()
            if (
                not description
                or len(description) > 160
                or not 0 < abs(amount) <= 99999999999
            ):
                skipped += 1
                continue
            entries.append(
                {
                    "source_index": len(entries),
                    "page": page["page"],
                    "line": line_number,
                    "date": parsed_date.isoformat(),
                    "description": description,
                    "amount_cents": abs(amount),
                    "kind": "refund" if amount < 0 else "expense",
                    "category": suggest_category(description),
                }
            )
            if len(entries) > 500:
                raise HTTPException(
                    422, "Documento excede 500 candidatos. Divida a importação."
                )
    if not entries:
        raise HTTPException(
            422,
            "Nenhum lançamento reconhecido. Formato suportado: data completa, descrição e valor em reais na mesma linha. Use CSV ou lançamento manual.",
        )
    return {
        "entries": entries,
        "skipped_lines": skipped,
        "pages": len(payload["pages"]),
        "empty_pages": payload.get("empty_pages", []),
        "warnings": [
            "Extração assistida: revise cada data, descrição, valor e estorno. Linhas não reconhecidas não serão importadas.",
            "Esta leitura não comprova que todos os lançamentos foram encontrados. Confira depois o total da fatura com o emissor.",
        ],
    }


def preview_key(token):
    return "pdf-preview:" + hashlib.sha256(token.encode()).hexdigest()


async def prepare_pdf(statement_id, content, user, session):
    if not content.startswith(b"%PDF-") or len(content) > MAX_PDF_BYTES:
        raise HTTPException(422, "Selecione um PDF válido de até 2 MB")
    try:
        result = await run_in_threadpool(extract_isolated, content)
    except (OSError, ValueError):
        raise HTTPException(
            503, "Leitor de PDF ocupado ou indisponível. Tente novamente ou use CSV."
        ) from None
    if isinstance(result, dict) and isinstance(result.get("error"), str):
        raise HTTPException(422, ERRORS.get(result["error"], ERRORS["invalid_pdf"]))
    try:
        result = Extraction.model_validate(result).model_dump()
    except ValidationError:
        raise HTTPException(
            503, "Leitor retornou uma resposta inválida. Tente novamente."
        ) from None
    output = candidates(result)
    token = secrets.token_hex(32)
    occurrences, source_keys = {}, []
    for entry in output["entries"]:
        canonical = f"{entry['date']}|{entry['description'].casefold()}|{entry['amount_cents']}|{entry['kind']}"
        occurrences[canonical] = occurrences.get(canonical, 0) + 1
        source_keys.append(
            hashlib.sha256(f"{canonical}|{occurrences[canonical]}".encode()).hexdigest()
        )
    metadata = {
        "owner": user,
        "statement_id": statement_id,
        "count": len(output["entries"]),
        "source_keys": source_keys,
        "session": hashlib.sha256(session["csrf"].encode()).hexdigest(),
    }
    await run_in_threadpool(
        security.store.setex, preview_key(token), PREVIEW_TTL, json.dumps(metadata)
    )
    return {**output, "preview_token": token, "expires_in": PREVIEW_TTL}


@router.post("/{statement_id}/import/pdf/preview")
async def preview(
    statement_id: str,
    request: Request,
    user=Depends(security.current_user),
    db: Session = Depends(db_session),
):
    # Não executar parser antes de autenticar e conferir o proprietário.
    statement = await run_in_threadpool(owned, db, Statement, user, statement_id)
    require_open(statement)
    await run_in_threadpool(active_statement_card, db, user, statement)
    if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
        raise HTTPException(415, "Envie o arquivo com Content-Type application/pdf")
    await run_in_threadpool(db.rollback)  # Libera a conexão enquanto o leitor trabalha.
    return await prepare_pdf(statement_id, await request.body(), user, request.session)


class ReviewedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_index: int = Field(strict=True, ge=0, le=499)
    date: date
    description: str = Field(min_length=1, max_length=160)
    amount_cents: int = Field(strict=True, gt=0, le=99999999999)
    kind: str
    category: str

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value):
        if value not in ("expense", "refund"):
            raise ValueError("Tipo inválido")
        return value

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        return ReviewInput.valid_category(value)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed: bool = Field(strict=True)
    entries: list[ReviewedCandidate] = Field(min_length=1, max_length=500)


@router.post("/{statement_id}/import/pdf/confirm")
def confirm(
    statement_id: str,
    body: Confirmation,
    request: Request,
    user=Depends(security.current_user),
    db: Session = Depends(db_session),
):
    statement = lock_statement(db, user, statement_id)
    require_open(statement)
    active_statement_card(db, user, statement)
    raw = security.store.get(preview_key(body.preview_token))
    metadata = json.loads(raw) if raw else {}
    if (
        metadata.get("owner") != user
        or metadata.get("statement_id") != statement_id
        or metadata.get("session")
        != hashlib.sha256(request.session["csrf"].encode()).hexdigest()
    ):
        raise HTTPException(
            410,
            "Prévia expirada ou não pertence a esta sessão/fatura. Leia o arquivo novamente.",
        )
    indexes = [entry.source_index for entry in body.entries]
    if (
        not body.reviewed
        or len(set(indexes)) != len(indexes)
        or max(indexes) >= metadata["count"]
    ):
        raise HTTPException(
            422, "Revise os candidatos e confirme a seleção sem repetir linhas"
        )
    # Ordem original preserva a contagem de ocorrências mesmo se o cliente reordenar a lista.
    entries = sorted(body.entries, key=lambda entry: entry.source_index)
    keys = [metadata["source_keys"][entry.source_index] for entry in entries]
    marks = reserve(db, user, "card", statement_id, keys)
    created = removed = 0
    for entry in entries:
        canonical = f"{entry.date}|{entry.description.casefold()}|{entry.amount_cents}|{entry.kind}"
        key = metadata["source_keys"][entry.source_index]
        mark = marks[key]
        if mark.version and not mark.resource_id:
            raise HTTPException(
                409, "Origem desfeita. Revise o vínculo pela importação CSV."
            )
        if mark.removed:
            removed += 1
            continue
        existing = (
            db.scalar(
                select(Charge).where(
                    Charge.owner == user, Charge.id == mark.resource_id
                )
            )
            if mark.resource_id
            else None
        )
        if mark.resource_id and existing is None:
            mark.removed = True
            removed += 1
            continue
        if existing:
            previous = f"{existing.date}|{existing.description.casefold()}|{existing.amount_cents}|{existing.kind}"
            if previous != canonical:
                raise HTTPException(
                    409,
                    "Uma linha já importada foi alterada. Corrija o lançamento existente antes de reimportar.",
                )
            continue
        row = Charge(
            owner=user,
            statement_id=statement_id,
            import_key=key,
            payload_hash=key,
            operation_id=str(uuid4()),
            installment=1,
            installments=1,
            reviewed=True,
            **entry.model_dump(exclude={"source_index"}),
        )
        db.add(row)
        db.flush()
        mark.resource_id = row.id
        mark.version += 1
        created += 1
    db.commit()
    return import_result(len(entries), created, removed)
