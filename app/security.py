import hashlib
import json
import secrets
from fastapi import HTTPException, Request
from redis import Redis
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool
from app.config import settings

store = Redis.from_url(
    settings().redis_url,
    decode_responses=True,
    socket_timeout=3,
    socket_connect_timeout=3,
)
COOKIE = "walleturbo_session"
SESSION_TTL = 1800
MAX_SESSION = 28800
LIMIT_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


def session_key(sid):
    return "session:" + hashlib.sha256(sid.encode()).hexdigest()


def current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "Entre na sua conta para continuar")
    return user


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        import time

        conf = settings()
        # Não confiar em X-Forwarded-For fornecido pelo cliente.
        peer = request.client.host if request.client else "unknown"
        path = request.url.path
        try:
            if path.startswith(("/api", "/auth")):
                key = "rate:" + hashlib.sha256(peer.encode()).hexdigest()
                limit = 120
                count = await run_in_threadpool(store.eval, LIMIT_SCRIPT, 1, key, 60)
                if count > limit:
                    return JSONResponse(
                        {"detail": "Muitas requisições. Tente em um minuto."},
                        429,
                        headers={"Retry-After": "60"},
                    )
            sid = request.cookies.get(COOKIE, "")
            raw = (
                await run_in_threadpool(store.get, session_key(sid))
                if len(sid) == 64
                else None
            )
            session = json.loads(raw) if raw else {}
            if session and time.time() - session.get("created", 0) > MAX_SESSION:
                await run_in_threadpool(store.delete, session_key(sid))
                session = {}
            request.scope["session"] = session
            if session.get("user") and path.startswith("/api"):
                owner_hash = hashlib.sha256(session["user"].encode()).hexdigest()
                count = await run_in_threadpool(
                    store.eval, LIMIT_SCRIPT, 1, "rate:user:" + owner_hash, 60
                )
                if count > 90:
                    return JSONResponse(
                        {"detail": "Limite de requisições da conta atingido"},
                        429,
                        headers={"Retry-After": "60"},
                    )
                if "/import/" in path:
                    count = await run_in_threadpool(
                        store.eval, LIMIT_SCRIPT, 1, "rate:import:" + owner_hash, 60
                    )
                    if count > 10:
                        return JSONResponse(
                            {"detail": "Limite de importações atingido"},
                            429,
                            headers={"Retry-After": "60"},
                        )
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if request.headers.get("origin") != conf.base_url:
                    return JSONResponse({"detail": "Origem não autorizada"}, 403)
                if path.startswith("/api") and not session.get("user"):
                    return JSONResponse(
                        {"detail": "Sessão encerrada. Entre novamente."}, 401
                    )
                if path.startswith("/api") and not secrets.compare_digest(
                    request.headers.get("x-csrf-token", ""),
                    session.get("csrf", secrets.token_hex(32)),
                ):
                    return JSONResponse({"detail": "Token de segurança inválido"}, 403)
            response = await call_next(request)
            if request.scope.get("logout"):
                if sid:
                    await run_in_threadpool(store.delete, session_key(sid))
                response.delete_cookie(COOKIE, path="/")
            elif session:
                if not raw or request.scope.get("rotate_session"):
                    if raw:
                        await run_in_threadpool(store.delete, session_key(sid))
                    sid = secrets.token_hex(32)
                session.setdefault("created", time.time())
                ttl = max(
                    1,
                    min(
                        SESSION_TTL,
                        int(MAX_SESSION - (time.time() - session["created"])),
                    ),
                )
                if raw and not request.scope.get("rotate_session"):
                    # Uma resposta concorrente não pode ressuscitar uma sessão revogada.
                    persisted = await run_in_threadpool(
                        store.set,
                        session_key(sid),
                        json.dumps(session),
                        ex=ttl,
                        xx=True,
                    )
                    if not persisted:
                        return response
                else:
                    await run_in_threadpool(
                        store.setex, session_key(sid), ttl, json.dumps(session)
                    )
                response.set_cookie(
                    COOKIE,
                    sid,
                    max_age=ttl,
                    httponly=True,
                    secure=conf.base_url.startswith("https://"),
                    samesite="lax",
                    path="/",
                )
        except Exception as exc:
            from redis.exceptions import RedisError

            if isinstance(exc, RedisError):
                return JSONResponse(
                    {"detail": "Serviço temporariamente indisponível"}, 503
                )
            raise
        return response


class BodyLimitMiddleware:
    """Limita bytes e tempo total de leitura, inclusive em transferências chunked."""

    def __init__(self, app, limit=300_000, timeout_seconds=10):
        self.app, self.limit, self.timeout_seconds = app, limit, timeout_seconds

    async def __call__(self, scope, receive, send):
        import asyncio

        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        import re
        from app.pdf_protocol import MAX_PDF_BYTES

        limit = (
            MAX_PDF_BYTES
            if re.fullmatch(
                r"/api/statements/[a-f0-9-]{36}/import/pdf/preview",
                scope.get("path", ""),
            )
            else self.limit
        )
        body = bytearray()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > limit:
                        return await JSONResponse(
                            {
                                "detail": "Corpo da requisição excede o limite deste endpoint"
                            },
                            413,
                        )(scope, receive, send)
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse(
                {"detail": "Tempo de envio da requisição excedido"}, 408
            )(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class ResponseHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from starlette.datastructures import MutableHeaders

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.update(
                    {
                        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                        "X-Content-Type-Options": "nosniff",
                        "Referrer-Policy": "no-referrer",
                        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                        "Cache-Control": "no-store",
                        "X-Frame-Options": "DENY",
                    }
                )
                if settings().base_url.startswith("https://"):
                    headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self.app(scope, receive, secure_send)
