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
from app.balances import router as balances_router
from app.planning import router as planning_router
from app.pdf_import import router as pdf_router
from app.db import (
    Transaction,
    Goal,
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
from app.cards import router as cards_router, owned, public, monthly_card_summary
from app.domain import Entry, GoalInput, parse_csv, import_keys, summarize
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
    version="0.5.0",
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
app.include_router(pdf_router)
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
        db.execute(select(Statement.id).limit(1))
        db.execute(select(Transaction.account_id).limit(1))
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
    fields = (
        Entry.model_fields if isinstance(row, Transaction) else GoalInput.model_fields
    )
    return {"id": row.id, **{key: getattr(row, key) for key in fields}}


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


@app.post("/api/transactions", status_code=201)
def create_entry(
    body: Entry, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    if body.account_id:
        owned(db, Account, user, body.account_id)
    entry = Transaction(owner=user, **body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return serialized(entry)


@app.put("/api/transactions/{entry_id}")
def update_entry(
    entry_id: str,
    body: Entry,
    user=Depends(current_user),
    db: DBSession = Depends(db_session),
):
    entry = db.scalar(
        select(Transaction).where(Transaction.id == entry_id, Transaction.owner == user)
    )
    if entry is None:
        raise HTTPException(404, "Lançamento não encontrado")
    if body.account_id:
        owned(db, Account, user, body.account_id)
    for key, value in body.model_dump().items():
        setattr(entry, key, value)
    db.commit()
    return serialized(entry)


@app.delete("/api/transactions/{entry_id}", status_code=204)
def delete_entry(
    entry_id: str, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    result = db.execute(
        delete(Transaction).where(Transaction.id == entry_id, Transaction.owner == user)
    )
    if not result.rowcount:
        raise HTTPException(404, "Lançamento não encontrado")
    db.commit()


class CSVInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=256000)
    account_id: str | None = Field(default=None, max_length=36)


@app.post("/api/import/preview")
def preview(body: CSVInput, user=Depends(current_user)):
    try:
        return {"entries": [e.model_dump() for e in parse_csv(body.content)]}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.post("/api/import/confirm")
def confirm(
    body: CSVInput, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    try:
        entries = parse_csv(body.content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if body.account_id:
        owned(db, Account, user, body.account_id)
    created = 0
    for entry, key in zip(entries, import_keys(entries)):
        entry.account_id = body.account_id
        if body.account_id:
            key = hashlib.sha256((body.account_id + "|" + key).encode()).hexdigest()
        try:
            with db.begin_nested():
                db.add(Transaction(owner=user, import_key=key, **entry.model_dump()))
                db.flush()
            created += 1
        except IntegrityError:
            if not db.scalar(
                select(Transaction.id).where(
                    Transaction.owner == user, Transaction.import_key == key
                )
            ):
                raise
    db.commit()
    return {"created": created, "duplicates": len(entries) - created}


@app.post("/api/goals", status_code=201)
def create_goal(
    body: GoalInput, user=Depends(current_user), db: DBSession = Depends(db_session)
):
    goal = Goal(owner=user, **body.model_dump())
    db.add(goal)
    db.commit()
    return serialized(goal)


@app.put("/api/goals/{goal_id}")
def update_goal(
    goal_id: str,
    body: GoalInput,
    user=Depends(current_user),
    db: DBSession = Depends(db_session),
):
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.owner == user))
    if not goal:
        raise HTTPException(404, "Meta não encontrada")
    for key, value in body.model_dump().items():
        setattr(goal, key, value)
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
    db.commit()
    request.session.clear()
    request.scope["logout"] = True
    return {"deleted": True}
