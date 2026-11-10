import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.config import settings
from app.entries import router as entries_router
from app.import_marks import reserve, result as import_result
from app.audit import router as audit_router
from app.operations import router as operations_router
from app.payment_corrections import router as payment_corrections_router
from app.lifecycle import router as lifecycle_router
from app.balances import router as balances_router
from app.planning import router as planning_router
from app.pdf_import import router as pdf_router
from app.ofx_import import router as ofx_router
from app.ofx_card import router as ofx_card_router
from app.ofx_relocation import router as ofx_relocation_router
from app.db import (
    Transaction,
    Goal,
    FinancialAudit,
    RequestReceipt,
    ImportMark,
    MonthPlan,
    OpeningBalance,
    Transfer,
    Budget,
    Account,
    Card,
    Statement,
    Charge,
    StatementPayment,
    db_session,
)
from app.cards import (
    router as cards_router,
    owned,
    public,
    monthly_card_summary,
    require_active,
)
from app.domain import GoalInput, parse_csv, import_keys, summarize
from app.import_review import (
    candidates,
    ExcludedIndices,
    Links,
    apply_links,
    select_rows,
    selection_result,
    CSVRelease,
    origin_state,
    release_link,
    OriginVersions,
    require_released_revision,
)
from app.security import (
    SecurityMiddleware,
    BodyLimitMiddleware,
    ResponseHeadersMiddleware,
    current_user,
    store,
)

conf = settings()
WEB = Path(__file__).resolve().parent.parent / "web"
oauth = OAuth()
if conf.oidc_issuer:
    oauth.register(
        "identity",
        client_id=conf.oidc_client_id,
        client_secret=conf.oidc_client_secret,
        server_metadata_url=conf.oidc_issuer.rstrip("/")
        + "/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile", "code_challenge_method": "S256"},
    )


@asynccontextmanager
async def lifespan(app):
    conf.validate_auth()
    yield


app = FastAPI(
    title="Walleturbo",
    version="0.22.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(SecurityMiddleware)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=(
        [urlparse(conf.base_url).hostname, "testserver"]
        if conf.app_env != "production"
        else [urlparse(conf.base_url).hostname]
    ),
)
app.add_middleware(ResponseHeadersMiddleware)
app.include_router(cards_router)
app.include_router(balances_router)
app.include_router(lifecycle_router)
app.include_router(audit_router)
app.include_router(operations_router)
app.include_router(entries_router)
app.include_router(payment_corrections_router)
app.include_router(pdf_router)
app.include_router(ofx_router)
app.include_router(ofx_card_router)
app.include_router(ofx_relocation_router)
app.include_router(planning_router)


@app.exception_handler(IntegrityError)
async def integrity_conflict(request, exc):
    return JSONResponse(
        {"detail": "Conflito de dados. Atualize a tela antes de tentar novamente."}, 409
    )


app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: DBSession = Depends(db_session)):
    try:
        db.execute(select(Statement.id, Statement.version).limit(1))
        db.execute(select(MonthPlan.version).limit(1))
        db.execute(select(Transaction.account_id).limit(1))
        db.execute(select(RequestReceipt.request_id).limit(1))
        db.execute(select(ImportMark.resource_id, ImportMark.version).limit(1))
        db.execute(select(Transaction.version, Transaction.request_id).limit(1))
        db.execute(select(Charge.correction_reason).limit(1))
        db.execute(
            select(StatementPayment.version, StatementPayment.correction_reason).limit(
                1
            )
        )
        db.execute(select(FinancialAudit.id).limit(1))
        db.execute(select(Goal.archived, Goal.version).limit(1))
        db.execute(select(Account.archived, Account.version).limit(1))
        db.execute(select(Card.archived, Card.version).limit(1))
        db.execute(select(OpeningBalance.id).limit(1))
        db.execute(select(Transfer.id).limit(1))
        store.ping()
    except Exception:
        raise HTTPException(503, "Dependências indisponíveis") from None
    return {"status": "ok"}


@app.get("/auth/login")
async def login(request: Request):
    if not conf.oidc_issuer:
        raise HTTPException(503, "Provedor de identidade ainda não configurado")
    return await oauth.identity.authorize_redirect(
        request,
        conf.base_url + "/auth/callback",
        acr_values=conf.required_acr,
        prompt="login",
    )


@app.get("/auth/callback")
async def callback(request: Request):
    if not conf.oidc_issuer:
        raise HTTPException(503, "Autenticação indisponível")
    try:
        token = await oauth.identity.authorize_access_token(request)
        claims = token.get("userinfo", {})
        if (
            not claims.get("sub")
            or claims.get("iss") != conf.oidc_issuer
            or claims.get("acr") != conf.required_acr
        ):
            raise HTTPException(403, "Autenticação com segundo fator obrigatória")
    except OAuthError:
        raise HTTPException(
            400, "Não foi possível validar o login. Tente novamente."
        ) from None
    request.session.clear()
    request.session.update(
        {
            "user": hashlib.sha256(
                (conf.oidc_issuer + "|" + claims["sub"]).encode()
            ).hexdigest(),
            "csrf": secrets.token_hex(32),
        }
    )
    request.scope["rotate_session"] = True
    return RedirectResponse("/", status_code=303)


@app.post("/api/logout")
def logout(request: Request, user=Depends(current_user)):
    request.session.clear()
    request.scope["logout"] = True
    return {"ok": True}


@app.get("/api/me")
def me(request: Request, user=Depends(current_user)):
    return {"csrf": request.session["csrf"]}


def serialized(row):
    return public(row)


@app.get("/api/dashboard")
def dashboard(
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    user=Depends(current_user),
    db: DBSession = Depends(db_session),
):
    year, m = map(int, month.split("-"))
    if not 1900 <= year <= 9998:
        raise HTTPException(422, "Ano inválido")
    start, end = date(year, m, 1), date(year + (m == 12), m % 12 + 1, 1)
    entries = list(
        db.scalars(
            select(Transaction)
            .where(
                Transaction.owner == user,
                Transaction.date >= start,
                Transaction.date < end,
            )
            .order_by(Transaction.date.desc(), Transaction.id)
        )
    )
    summary = summarize(entries)
    card = monthly_card_summary(db, user, month)
    summary["cash_balance_cents"] = (
        summary["balance_cents"] - card["card_payment_cents"]
    )
    summary["expense_cents"] += card["card_expense_cents"]
    summary["balance_cents"] -= card["card_expense_cents"]
    summary["pending"] += card["card_pending"]
    for category, amount in card["card_categories"].items():
        summary["categories"][category] = (
            summary["categories"].get(category, 0) + amount
        )
    # Os alertas consideram o consumo; pagamento de fatura não é outra despesa.
    summary["insights"] = []
    if summary["categories"].get("Assinaturas", 0) > 0:
        summary["insights"].append(
            {
                "title": "Revise suas assinaturas",
                "description": "Total registrado na categoria, incluindo cartões. Não é economia garantida.",
                "amount_cents": summary["categories"]["Assinaturas"],
            }
        )
    if summary["balance_cents"] < 0:
        summary["insights"].append(
            {
                "title": "Despesas acima das entradas",
                "description": "Inclui parcelas pelo mês de vencimento. Confira se registrou todas as receitas.",
                "amount_cents": -summary["balance_cents"],
            }
        )
    return {
        **summary,
        **card,
        "transactions": [serialized(row) for row in entries],
        "goals": [
            serialized(row)
            for row in db.scalars(
                select(Goal).where(Goal.owner == user).order_by(Goal.deadline)
            )
        ],
    }


class CSVInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=256000)
    account_id: str | None = Field(default=None, max_length=36)
    excluded_indices: ExcludedIndices = Field(default_factory=list)
    links: Links = Field(default_factory=list)
    origin_versions: OriginVersions = Field(default_factory=list)


class TransactionCSVRelease(CSVRelease):
    account_id: str | None = Field(default=None, max_length=36)


def transaction_import_keys(entries, account_id):
    keys = import_keys(entries)
    return (
        [hashlib.sha256((account_id + "|" + key).encode()).hexdigest() for key in keys]
        if account_id
        else keys
    )


@app.post("/api/import/unlink")
def unlink_csv(
    body: TransactionCSVRelease,
    user=Depends(current_user),
    db: DBSession = Depends(db_session),
):
    try:
        entries = parse_csv(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if body.account_id:
        require_active(owned(db, Account, user, body.account_id, lock=True))
    return release_link(
        db,
        Transaction,
        user,
        transaction_import_keys(entries, body.account_id),
        body.release,
        Transaction.account_id == body.account_id,
        "transaction",
        "",
    )


@app.post("/api/import/preview")
def preview(
    body: CSVInput, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    try:
        entries = parse_csv(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if body.account_id:
        require_active(owned(db, Account, user, body.account_id))
    return {
        "entries": [e.model_dump() for e in entries],
        **origin_state(
            db,
            Transaction,
            user,
            transaction_import_keys(entries, body.account_id),
            Transaction.account_id == body.account_id,
            "transaction",
            "",
        ),
        "possible_duplicates": candidates(
            db, Transaction, user, entries, Transaction.account_id == body.account_id
        ),
    }


@app.post("/api/import/confirm")
def confirm(
    body: CSVInput, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    try:
        entries = parse_csv(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if body.account_id:
        require_active(owned(db, Account, user, body.account_id, lock=True))
    keys = transaction_import_keys(entries, body.account_id)
    selected = select_rows(entries, keys, body.excluded_indices)
    marks = reserve(db, user, "transaction", "", [key for _, key in selected])
    linked = apply_links(
        db,
        Transaction,
        user,
        entries,
        keys,
        body.excluded_indices,
        body.links,
        marks,
        Transaction.account_id == body.account_id,
        "transaction",
        "",
    )
    created = removed = 0
    indices = {key: index for index, key in enumerate(keys)}
    for entry, key in selected:
        mark = marks[key]
        require_released_revision(mark, body.origin_versions, indices[key])
        if mark.removed:
            removed += 1
            continue
        if mark.resource_id:
            if not db.scalar(
                select(Transaction.id).where(
                    Transaction.owner == user, Transaction.id == mark.resource_id
                )
            ):
                mark.removed = True
                removed += 1
            continue
        entry.account_id = body.account_id
        row = Transaction(owner=user, import_key=key, **entry.model_dump())
        db.add(row)
        db.flush()
        mark.resource_id = row.id
        mark.version += 1
        created += 1
    db.commit()
    output = selection_result(
        len(entries), created, removed, len(body.excluded_indices)
    )
    if linked:
        output["linked"] = linked
    return output


@app.post("/api/goals", status_code=201)
def create_goal(
    body: GoalInput, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    goal = Goal(owner=user, **body.model_dump())
    db.add(goal)
    db.commit()
    return serialized(goal)


@app.get("/api/privacy/export")
def export(user=Depends(current_user), db: DBSession = Depends(db_session)):
    return {
        "transactions": [
            serialized(t)
            for t in db.scalars(select(Transaction).where(Transaction.owner == user))
        ],
        "goals": [
            serialized(g) for g in db.scalars(select(Goal).where(Goal.owner == user))
        ],
        **{
            name: [
                public(row)
                for row in db.scalars(select(model).where(model.owner == user))
            ]
            for name, model in [
                ("import_marks", ImportMark),
                ("request_receipts", RequestReceipt),
                ("financial_history", FinancialAudit),
                ("accounts", Account),
                ("opening_balances", OpeningBalance),
                ("transfers", Transfer),
                ("cards", Card),
                ("statements", Statement),
                ("card_charges", Charge),
                ("statement_payments", StatementPayment),
                ("month_plans", MonthPlan),
                ("budgets", Budget),
            ]
        },
    }


@app.delete("/api/privacy/data")
def erase(
    request: Request, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    if request.headers.get("x-confirm-delete") != "EXCLUIR":
        raise HTTPException(400, "Confirmação explícita necessária")
    for model in (Transfer, OpeningBalance, StatementPayment, Charge, Statement):
        db.execute(delete(model).where(model.owner == user))
    db.execute(delete(Transaction).where(Transaction.owner == user))
    db.execute(delete(Goal).where(Goal.owner == user))
    for model in (Card, Account, MonthPlan, Budget):
        db.execute(delete(model).where(model.owner == user))
    db.execute(delete(ImportMark).where(ImportMark.owner == user))
    db.execute(delete(RequestReceipt).where(RequestReceipt.owner == user))
    db.execute(delete(FinancialAudit).where(FinancialAudit.owner == user))
    db.commit()
    request.session.clear()
    request.scope["logout"] = True
    return {"deleted": True}
